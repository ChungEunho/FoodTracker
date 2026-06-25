"""
Brand/menu nutrition search service — port of nutrition_search.py for the FastAPI backend.

Search tiers (same logic as the original, API keys replaced with settings):
  Korean input: MFDS DB → SerpAPI (Google search + LLM parse) → LLM direct estimate
  English input: MFDS DB → CalorieNinjas → SerpAPI → LLM direct estimate

Each tier skips silently if the required API key is absent.
The progress_cb parameter is dropped — callers poll the result directly via the
job/status pattern instead of streaming progress messages.

LLM calls consume rate-limit slots via rate_limiter.consume().
HTTP calls to MFDS, SerpAPI, and CalorieNinjas use httpx (async) to avoid
blocking the event loop.  The synchronous `requests` library from the original
is replaced with `httpx.AsyncClient` throughout.
"""

import asyncio
import json
import logging
import re
import urllib.parse

import httpx

from app.config import settings
from app.services import rate_limiter
from app.services.openrouter_client import get_client, strip_fence

logger = logging.getLogger(__name__)

# ── Language detection ────────────────────────────────────────────────────────

_KO_RE = re.compile(r"[가-힣㄰-㆏ᄀ-ᇿ]")


def _is_korean(text: str) -> bool:
    return bool(_KO_RE.search(text))


# ── Common utilities ──────────────────────────────────────────────────────────

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


# ════════════════════════════════════════════════════════════════════════════
# Tier 1: 식품안전처 공공데이터 API
# ════════════════════════════════════════════════════════════════════════════
# Response fields (per 100 g):
#   AMT_NUM1 = energy (kcal)
#   AMT_NUM3 = protein (g)
#   AMT_NUM4 = fat (g)
#   AMT_NUM6 = carbohydrates (g)
#   AMT_NUM7 = sugars (g)

_MFDS_BASE = (
    "https://apis.data.go.kr/1471000/FoodNtrCpntDbInfo02"
    "/getFoodNtrCpntDbInq02"
)


def _mfds_match_score(item: dict, query_words: list[str]) -> int:
    name = item.get("FOOD_NM_KR", "").lower()
    return sum(1 for w in query_words if w in name)


async def _mfds_search(query: str) -> dict | None:
    key = settings.data_go_kr_food_api_key.strip()
    if not key:
        return None

    encoded_food = urllib.parse.quote(query)
    url = (
        f"{_MFDS_BASE}"
        f"?serviceKey={key}"
        f"&pageNo=1&numOfRows=10"
        f"&foodNm={encoded_food}"
        f"&type=json"
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            items = resp.json().get("body", {}).get("items", [])
        if not items:
            return None
        if isinstance(items, dict):
            items = [items]

        query_words = [w for w in query.lower().split() if len(w) > 1]
        scored = sorted(
            items, key=lambda x: _mfds_match_score(x, query_words), reverse=True
        )
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


# ════════════════════════════════════════════════════════════════════════════
# Tier 2 (Korean): SerpAPI — Google search snippets → LLM parse
# ════════════════════════════════════════════════════════════════════════════

_SERPAPI_URL = "https://serpapi.com/search.json"


async def _serpapi_fetch_snippets(query: str, korean: bool) -> str | None:
    """Fetch Google search result text via SerpAPI."""
    key = settings.serpapi_api_key.strip()
    if not key:
        return None

    search_q = f"{query} {'칼로리 영양성분' if korean else 'calories nutrition facts'}"
    params = {
        "engine":  "google",
        "q":       search_q,
        "api_key": key,
        "num":     5,
        "gl":      "kr",
        "hl":      "ko" if korean else "en",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(_SERPAPI_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        parts: list[str] = []

        # answer_box (Google AI overview / featured snippet)
        ab = data.get("answer_box", {})
        for field in ("answer", "snippet", "snippet_highlighted_words"):
            val = ab.get(field)
            if isinstance(val, list):
                val = " ".join(val)
            if val:
                parts.append(str(val))

        # knowledge_graph
        kg = data.get("knowledge_graph", {})
        if desc := kg.get("description"):
            parts.append(desc)

        # organic results
        for item in data.get("organic_results", [])[:4]:
            if snip := item.get("snippet"):
                parts.append(snip)

        return "\n\n".join(parts) if parts else None
    except Exception:
        return None


def _parse_nutrition_from_snippets_sync(query: str, snippets: str, korean: bool) -> dict | None:
    """
    Synchronous LLM call to parse structured nutrition from search result snippets.
    Wrapped in run_in_executor by the async caller.
    """
    if korean:
        prompt = (
            f'다음은 "{query}"에 대한 구글 검색 결과입니다:\n\n'
            f"---\n{snippets}\n---\n\n"
            "위 검색 결과를 바탕으로 영양성분을 JSON으로 추출하세요.\n"
            '{"found":true,"product_name":"제품명",'
            '"items":[{"name":"제품명","weight_g":473,"calories_kcal":165,'
            '"carbs_g":29,"protein_g":3,"fat_g":2,"sugar_g":28}]}\n\n'
            "규칙:\n"
            "- 검색 결과에 명시된 수치를 최우선으로 사용\n"
            "- 그란데/Large/Venti 등 사이즈 명시 시 해당 사이즈 기준\n"
            "- 사이즈 미명시 시 기본 1회 제공량 기준\n"
            '- 검색 결과에 관련 수치가 전혀 없으면: {"found": false}\n'
            "- 정수값, JSON만 출력"
        )
    else:
        prompt = (
            f'Google search results for "{query}":\n\n'
            f"---\n{snippets}\n---\n\n"
            'Extract nutrition facts as JSON: {"found":true,"product_name":"name",'
            '"items":[{"name":"name","weight_g":355,"calories_kcal":5,'
            '"carbs_g":1,"protein_g":0,"fat_g":0,"sugar_g":0}]}\n\n'
            "Use numbers from search results. Specified size if mentioned. "
            'Return {"found":false} only if no nutrition numbers found. '
            "Integer values, JSON only."
        )

    try:
        c = get_client()
        response = c.chat.completions.create(
            model="openai/gpt-oss-120b:free",
            messages=[{"role": "user", "content": prompt}],
        )
        raw = strip_fence(response.choices[0].message.content.strip())
        data = json.loads(raw)
        if data.get("found") and data.get("items"):
            return data
    except Exception:
        pass
    return None


async def _serpapi_search(query: str, korean: bool) -> dict | None:
    snippets = await _serpapi_fetch_snippets(query, korean)
    if not snippets:
        return None
    # LLM call — consume one rate-limit slot
    await rate_limiter.consume()
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _parse_nutrition_from_snippets_sync, query, snippets, korean
    )


# ════════════════════════════════════════════════════════════════════════════
# Tier 2 (English): CalorieNinjas API
# ════════════════════════════════════════════════════════════════════════════

_CN_URL = "https://api.calorieninjas.com/v1/nutrition"


async def _calorieninjas_search(query_en: str, display_name: str) -> dict | None:
    key = settings.calorie_ninja_api_key.strip()
    if not key:
        return None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                _CN_URL,
                params={"query": query_en},
                headers={"X-Api-Key": key},
            )
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

        return {
            "name":          display_name,
            "weight_g":      round(serving_g) or 100,
            "calories_kcal": round(calories),
            "carbs_g":       round(carbs),
            "protein_g":     round(protein),
            "fat_g":         round(fat),
            "sugar_g":       round(sugar),
        }
    except Exception:
        return None


# ════════════════════════════════════════════════════════════════════════════
# Tier 3/4: LLM direct estimate
# ════════════════════════════════════════════════════════════════════════════

def _llm_lookup_sync(brand: str, menu: str, korean: bool) -> dict | None:
    """Synchronous LLM direct nutrition estimate. Wrapped in run_in_executor by caller."""
    query = f"{brand} {menu}".strip()

    if korean:
        prompt = (
            f'다음 제품의 영양성분을 알려주세요: "{query}"\n\n'
            "JSON 형식으로만 응답 (마크다운 없이):\n"
            '{"found":true,"product_name":"제품명",'
            '"items":[{"name":"제품명","weight_g":473,"calories_kcal":165,'
            '"carbs_g":29,"protein_g":3,"fat_g":2,"sugar_g":28}]}\n\n'
            "규칙:\n"
            "- 공식 영양성분표, 브랜드 웹사이트, 일반 영양 지식 등 모든 출처 활용\n"
            "- 정확한 수치를 모를 때는 합리적인 추정값 제공 (추정도 허용)\n"
            "- 그란데/Large/Venti 등 사이즈 명시 시 해당 사이즈 기준\n"
            "- 사이즈 미명시 시 기본 1회 제공량(Tall/Regular) 기준\n"
            '- 해당 제품·브랜드 자체를 전혀 모를 때만: {"found": false}\n'
            "- 정수값, JSON만 출력"
        )
    else:
        prompt = (
            f'Provide nutrition facts for: "{query}"\n\n'
            'Return JSON only: {"found":true,"product_name":"name",'
            '"items":[{"name":"name","weight_g":150,"calories_kcal":400,'
            '"carbs_g":45,"protein_g":20,"fat_g":15,"sugar_g":8}]}\n\n'
            "Rules: use any available source; estimates allowed; "
            "use specified size (Grande/Large/Venti) if mentioned, otherwise default serving; "
            'only {"found":false} if product is completely unknown; '
            "integer values, JSON only"
        )

    try:
        c = get_client()
        response = c.chat.completions.create(
            model="openai/gpt-oss-120b:free",
            messages=[{"role": "user", "content": prompt}],
        )
        raw = strip_fence(response.choices[0].message.content.strip())
        data = json.loads(raw)
        if data.get("found") and data.get("items"):
            return data
    except Exception:
        pass
    return None


async def _llm_lookup(brand: str, menu: str, korean: bool) -> dict | None:
    """Async wrapper for LLM direct estimate. Consumes one rate-limit slot."""
    await rate_limiter.consume()
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _llm_lookup_sync, brand, menu, korean)


# ════════════════════════════════════════════════════════════════════════════
# Public API
# ════════════════════════════════════════════════════════════════════════════

async def search_nutrition(
    brand: str, menu: str
) -> tuple[dict | None, str | None, bool]:
    """
    Search for nutrition information for a brand/menu combination.

    Search order:
      Korean: MFDS DB → SerpAPI (Google + LLM parse) → LLM direct estimate
      English: MFDS DB → CalorieNinjas → SerpAPI → LLM direct estimate

    Args:
        brand: Brand name (e.g. "스타벅스"). May be empty if menu is provided.
        menu:  Menu item name (e.g. "아이스 아메리카노 그란데"). May be empty if brand is provided.

    Returns:
        Tuple of (result_dict, found_name, is_exact):
          - result_dict: {"items": [...], "total": {...}} or None if not found.
          - found_name:  The product name matched (may differ from query).
          - is_exact:    True if the match came from a structured data source.
    """
    query = f"{brand} {menu}".strip()
    korean = _is_korean(query)

    # ── Tier 1: 식품안전처 ────────────────────────────────────────────────────
    mfds = await _mfds_search(query)
    if mfds:
        return _build_result([mfds]), mfds["name"], True

    # ── Tier 2 (Korean): SerpAPI Google search ────────────────────────────────
    if korean:
        serp = await _serpapi_search(query, korean=True)
        if serp:
            return _build_result(serp["items"]), serp.get("product_name", query), True

    # ── Tier 2 (English): CalorieNinjas → SerpAPI ───────────────────────────
    else:
        cn = await _calorieninjas_search(query, display_name=menu or query)
        if cn:
            return _build_result([cn]), query, True

        serp = await _serpapi_search(query, korean=False)
        if serp:
            return _build_result(serp["items"]), serp.get("product_name", query), True

    # ── Final tier: LLM direct estimate ─────────────────────────────────────
    llm = await _llm_lookup(brand, menu, korean)
    if llm:
        return _build_result(llm["items"]), llm.get("product_name", query), True

    return None, None, False
