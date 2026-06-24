"""
nutrition_search.py — 3단계 영양정보 검색

1순위: 식품안전처 공공데이터 API  (DATA_GO_KR_FOOD_API_KEY)
2순위: SerpAPI Google 검색        (SERPAPI_API_KEY, 한국어 전용)
2순위: CalorieNinjas API          (CALORIE_NINJA_API_KEY, 영어 쿼리 전용)
3순위: LLM 직접 추정              (OpenRouter)
"""
import json
import os
import re
import urllib.parse
from typing import Callable

import requests
from client import client, strip_fence

_KO_RE = re.compile(r"[가-힣㄰-㆏ᄀ-ᇿ]")

def _is_korean(text: str) -> bool:
    return bool(_KO_RE.search(text))


def _build_result(items: list[dict]) -> dict:
    keys = ("weight_g", "calories_kcal", "carbs_g", "protein_g", "fat_g", "sugar_g")
    total = {k: sum(it.get(k, 0) for it in items) for k in keys}
    return {"items": items, "total": total}


def _safe_float(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _per_serving(per100: float, serving_g: float) -> int:
    return round(per100 * serving_g / 100)


_MFDS_BASE = "https://apis.data.go.kr/1471000/FoodNtrCpntDbInfo02/getFoodNtrCpntDbInq02"


def _mfds_match_score(item: dict, query_words: list[str]) -> int:
    name = item.get("FOOD_NM_KR", "").lower()
    return sum(1 for w in query_words if w in name)


def _mfds_search(query: str) -> dict | None:
    key = os.environ.get("DATA_GO_KR_FOOD_API_KEY", "").strip()
    if not key:
        return None
    encoded_food = urllib.parse.quote(query)
    url = f"{_MFDS_BASE}?serviceKey={key}&pageNo=1&numOfRows=10&foodNm={encoded_food}&type=json"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        items = resp.json().get("body", {}).get("items", [])
        if not items:
            return None
        if isinstance(items, dict):
            items = [items]
        query_words = [w for w in query.lower().split() if len(w) > 1]
        scored = sorted(items, key=lambda x: _mfds_match_score(x, query_words), reverse=True)
        best = scored[0]
        if _mfds_match_score(best, query_words) == 0:
            return None
        food_name = best.get("FOOD_NM_KR", query)
        serving_str = best.get("SERVING_SIZE", "100g")
        try:
            serving_g = float(re.sub(r"[^\d.]", "", serving_str) or "100")
        except ValueError:
            serving_g = 100.0
        return {
            "name":          food_name,
            "weight_g":      int(serving_g),
            "calories_kcal": _per_serving(_safe_float(best.get("AMT_NUM1")), serving_g),
            "protein_g":     _per_serving(_safe_float(best.get("AMT_NUM3")), serving_g),
            "fat_g":         _per_serving(_safe_float(best.get("AMT_NUM4")), serving_g),
            "carbs_g":       _per_serving(_safe_float(best.get("AMT_NUM6")), serving_g),
            "sugar_g":       _per_serving(_safe_float(best.get("AMT_NUM7")), serving_g),
        }
    except Exception:
        return None


_SERPAPI_URL = "https://serpapi.com/search.json"


def _serpapi_fetch_snippets(query: str, korean: bool) -> str | None:
    key = os.environ.get("SERPAPI_API_KEY", "").strip()
    if not key:
        return None
    search_q = f"{query} {'칼로리 영양성분' if korean else 'calories nutrition facts'}"
    params = {"engine": "google", "q": search_q, "api_key": key, "num": 5, "gl": "kr", "hl": "ko" if korean else "en"}
    try:
        resp = requests.get(_SERPAPI_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        parts: list[str] = []
        ab = data.get("answer_box", {})
        for field in ("answer", "snippet", "snippet_highlighted_words"):
            val = ab.get(field)
            if isinstance(val, list):
                val = " ".join(val)
            if val:
                parts.append(str(val))
        kg = data.get("knowledge_graph", {})
        if desc := kg.get("description"):
            parts.append(desc)
        for item in data.get("organic_results", [])[:4]:
            if snip := item.get("snippet"):
                parts.append(snip)
        return "\n\n".join(parts) if parts else None
    except Exception:
        return None


def _parse_nutrition_from_snippets(query: str, snippets: str, korean: bool) -> dict | None:
    if korean:
        prompt = (f'다음은 "{query}"에 대한 구글 검색 결과입니다:\n\n---\n{snippets}\n---\n\n'
                  '위 검색 결과를 바탕으로 영양성분을 JSON으로 추출하세요.\n'
                  '{"found":true,"product_name":"제품명","items":[{"name":"제품명","weight_g":473,"calories_kcal":165,"carbs_g":29,"protein_g":3,"fat_g":2,"sugar_g":28}]}\n\n'
                  '규칙:\n- 검색 결과에 명시된 수치를 최우선으로 사용\n- 그란데/Large/Venti 등 사이즈 명시 시 해당 사이즈 기준\n- 검색 결과에 관련 수치가 전혀 없으면: {"found": false}\n- 정수값, JSON만 출력')
    else:
        prompt = (f'Google search results for "{query}":\n\n---\n{snippets}\n---\n\n'
                  'Extract nutrition facts as JSON: {"found":true,"product_name":"name","items":[{"name":"name","weight_g":355,"calories_kcal":5,"carbs_g":1,"protein_g":0,"fat_g":0,"sugar_g":0}]}\n\n'
                  'Use numbers from search results. Return {"found":false} only if no nutrition numbers found. Integer values, JSON only.')
    try:
        response = client.chat.completions.create(model="openai/gpt-oss-120b:free", messages=[{"role": "user", "content": prompt}])
        raw = strip_fence(response.choices[0].message.content.strip())
        data = json.loads(raw)
        if data.get("found") and data.get("items"):
            return data
    except Exception:
        pass
    return None


def _serpapi_search(query: str, korean: bool) -> dict | None:
    snippets = _serpapi_fetch_snippets(query, korean)
    if not snippets:
        return None
    return _parse_nutrition_from_snippets(query, snippets, korean)


_CN_URL = "https://api.calorieninjas.com/v1/nutrition"


def _calorieninjas_search(query_en: str, display_name: str) -> dict | None:
    key = os.environ.get("CALORIE_NINJA_API_KEY", "").strip()
    if not key:
        return None
    try:
        resp = requests.get(_CN_URL, params={"query": query_en}, headers={"X-Api-Key": key}, timeout=10)
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            return None
        serving_g = sum(_safe_float(it.get("serving_size_g", 0)) for it in items)
        calories  = sum(_safe_float(it.get("calories", 0)) for it in items)
        carbs     = sum(_safe_float(it.get("carbohydrates_total_g", 0)) for it in items)
        protein   = sum(_safe_float(it.get("protein_g", 0)) for it in items)
        fat       = sum(_safe_float(it.get("fat_total_g", 0)) for it in items)
        sugar     = sum(_safe_float(it.get("sugar_g", 0)) for it in items)
        return {"name": display_name, "weight_g": round(serving_g) or 100, "calories_kcal": round(calories), "carbs_g": round(carbs), "protein_g": round(protein), "fat_g": round(fat), "sugar_g": round(sugar)}
    except Exception:
        return None


def _llm_lookup(brand: str, menu: str, korean: bool) -> dict | None:
    query = f"{brand} {menu}".strip()
    if korean:
        prompt = (f'다음 제품의 영양성분을 알려주세요: "{query}"\n\n'
                  'JSON 형식으로만 응답:\n{"found":true,"product_name":"제품명","items":[{"name":"제품명","weight_g":473,"calories_kcal":165,"carbs_g":29,"protein_g":3,"fat_g":2,"sugar_g":28}]}\n\n'
                  '규칙:\n- 모든 출처 활용, 추정도 허용\n- 사이즈 명시 시 해당 사이즈 기준\n- 전혀 모를 때만: {"found": false}\n- 정수값, JSON만 출력')
    else:
        prompt = (f'Provide nutrition facts for: "{query}"\n\n'
                  'Return JSON only: {"found":true,"product_name":"name","items":[{"name":"name","weight_g":150,"calories_kcal":400,"carbs_g":45,"protein_g":20,"fat_g":15,"sugar_g":8}]}\n\n'
                  'Rules: estimates allowed; specified size if mentioned; only {"found":false} if completely unknown; integer values, JSON only')
    try:
        response = client.chat.completions.create(model="openai/gpt-oss-120b:free", messages=[{"role": "user", "content": prompt}])
        raw = strip_fence(response.choices[0].message.content.strip())
        data = json.loads(raw)
        if data.get("found") and data.get("items"):
            return data
    except Exception:
        pass
    return None


def search_nutrition(brand: str, menu: str, progress_cb: Callable[[str], None] | None = None):
    """
    영양정보 검색.
    한국어: MFDS → SerpAPI(Google+LLM파싱) → LLM 추정
    영어:   MFDS → CalorieNinjas → SerpAPI → LLM 추정
    """
    def _cb(msg: str):
        if progress_cb:
            progress_cb(msg)

    query = f"{brand} {menu}".strip()
    korean = _is_korean(query)

    _cb("🏛️ 1순위: 식품안전처 DB 검색 중…")
    mfds = _mfds_search(query)
    if mfds:
        _cb("✅ 식품안전처 DB에서 찾았습니다.")
        return _build_result([mfds]), mfds["name"], True

    if korean:
        _cb("🌐 2순위: Google 검색 중… (SerpAPI)")
        serp = _serpapi_search(query, korean=True)
        if serp:
            _cb("✅ Google 검색 결과에서 찾았습니다.")
            return _build_result(serp["items"]), serp.get("product_name", query), True
    else:
        _cb("🌐 2순위: CalorieNinjas 검색 중…")
        cn = _calorieninjas_search(query, display_name=menu or query)
        if cn:
            _cb("✅ CalorieNinjas에서 찾았습니다.")
            return _build_result([cn]), query, True
        _cb("🌐 3순위: Google 검색 중… (SerpAPI)")
        serp = _serpapi_search(query, korean=False)
        if serp:
            _cb("✅ Google 검색 결과에서 찾았습니다.")
            return _build_result(serp["items"]), serp.get("product_name", query), True

    tier = "3순위" if korean else "4순위"
    _cb(f"🤖 {tier}: AI 직접 추정 중…")
    llm = _llm_lookup(brand, menu, korean)
    if llm:
        return _build_result(llm["items"]), llm.get("product_name", query), True

    return None, None, False
