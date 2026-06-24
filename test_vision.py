"""
test_vision.py — 비전 모델 실제 응답 테스트 (타이밍 + 오류 분류 포함)
"""
import sys, time, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
from _paths import env_path
load_dotenv(env_path())

import base64, io
from PIL import Image as PILImage
from client import client, strip_fence

_MODELS = [
    "google/gemini-2.0-flash-exp:free",
    "qwen/qwen2.5-vl-72b-instruct:free",
    "meta-llama/llama-3.2-90b-vision-instruct:free",
    "nvidia/nemotron-nano-12b-v2-vl:free",
]

SYSTEM_PROMPT = """You are a food recognition expert. Analyze the food image and return a JSON object listing every food item visible.
Output format (JSON only, no markdown):
{"items":[{"name":"음식명 (Korean name preferred)","cooking_method":"조리법","notes":"특이사항"}],"raw_description":"brief description"}
Rules: Use Korean names. Output valid JSON only."""

def img_to_url(path: Path) -> str:
    img = PILImage.open(path).convert("RGB")
    if max(img.size) > 1024:
        img.thumbnail((1024, 1024), PILImage.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.standard_b64encode(buf.getvalue()).decode()

def test_image(img_path: Path):
    print(f"\n{'='*60}")
    print(f"이미지: {img_path.name}")
    print(f"크기: {img_path.stat().st_size / 1024:.0f} KB")
    print(f"{'='*60}")

    data_url = img_to_url(img_path)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": data_url}},
            {"type": "text", "text": "이 음식 사진을 분석해줘."},
        ]},
    ]

    for model_id in _MODELS:
        print(f"\n  → 모델 시도: {model_id}")
        t0 = time.time()
        try:
            resp = client.chat.completions.create(
                model=model_id,
                messages=messages,
                timeout=30,
            )
            elapsed = time.time() - t0
            content = resp.choices[0].message.content if resp.choices else ""
            if content:
                print(f"  ✅ 성공 ({elapsed:.1f}초)")
                raw = strip_fence(content.strip())
                try:
                    parsed = json.loads(raw)
                    items = parsed.get("items", [])
                    print(f"  인식 결과: {[it.get('name','?') for it in items]}")
                    print(f"  전체 설명: {parsed.get('raw_description','')}")
                except Exception:
                    print(f"  원본 응답: {content[:200]}")
                return model_id
            else:
                print(f"  ⚠️  빈 응답 ({elapsed:.1f}초) — 다음 모델로")
        except Exception as e:
            elapsed = time.time() - t0
            err = str(e)
            if "429" in err or "rate" in err.lower():
                print(f"  🚫 Rate Limited ({elapsed:.1f}초): {err[:120]}")
            elif "402" in err or "credit" in err.lower() or "billing" in err.lower():
                print(f"  💳 크레딧/결제 필요 ({elapsed:.1f}초): {err[:120]}")
            elif "timeout" in err.lower() or "timed out" in err.lower():
                print(f"  ⏱️  타임아웃 ({elapsed:.1f}초) — 다음 모델로")
            else:
                print(f"  ❌ 오류 ({elapsed:.1f}초): {err[:120]}")
    print("\n  ❌ 모든 모델 실패")
    return None

if __name__ == "__main__":
    folder = Path(__file__).parent / "dist" / "example pictures"
    images = sorted(folder.glob("*.png")) + sorted(folder.glob("*.jpg"))
    print(f"테스트할 이미지: {len(images)}개")
    for img in images:
        test_image(img)
    print("\n\n✅ 테스트 완료")
