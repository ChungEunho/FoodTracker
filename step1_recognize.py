import base64
import concurrent.futures
import io
import json
import sys
from pathlib import Path
from client import client, strip_fence

try:
    from PIL import Image as _PilImage
    _PIL = True
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
        _HEIF = True
    except ImportError:
        _HEIF = False
except ImportError:
    _PIL = False
    _HEIF = False

_MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10MB
_MAX_DIMENSION = 1024  # 큰 이미지는 전송 속도 저하 → 1024로 제한
_MODEL_TIMEOUT = 30    # 모델별 하드 타임아웃(초) — ThreadPoolExecutor로 강제 적용

SYSTEM_PROMPT = """You are a food recognition expert. Analyze the food image and return a JSON object listing every food item visible.

Output format (JSON only, no markdown):
{
  "items": [
    {
      "name": "음식명 (Korean name preferred)",
      "cooking_method": "조리법 (e.g. 볶음/구이/삶음/생식/튀김)",
      "notes": "특이사항 (e.g. 소스 별도, 약 1공기 추정)"
    }
  ],
  "raw_description": "brief overall description of the meal"
}

Rules:
- List every distinct food item separately
- Use Korean names when possible
- If uncertain, include your best guess with a note
- Output valid JSON only"""


def _to_data_url(path: Path) -> str:
    if _PIL:
        img = _PilImage.open(path).convert("RGB")
        if max(img.size) > _MAX_DIMENSION:
            img.thumbnail((_MAX_DIMENSION, _MAX_DIMENSION), _PilImage.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        encoded = base64.standard_b64encode(buf.getvalue()).decode()
        return f"data:image/jpeg;base64,{encoded}"

    suffix = path.suffix.lower()
    mime = "image/jpeg" if suffix in (".jpg", ".jpeg") else "image/png"
    with open(path, "rb") as f:
        return f"data:{mime};base64,{base64.standard_b64encode(f.read()).decode()}"


def recognize(image_path: str) -> dict:
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {image_path}")
    suffix = path.suffix.lower()
    allowed = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"}
    if suffix not in allowed:
        raise ValueError(f"지원하지 않는 형식입니다 (JPEG/PNG/WebP/HEIC만 허용): {suffix}")

    size = path.stat().st_size
    if size > _MAX_IMAGE_BYTES:
        print(f"경고: 이미지 크기가 큽니다 ({size / 1024 / 1024:.1f}MB > 10MB).")

    data_url = _to_data_url(path)

    _MESSAGES = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_url}},
                {"type": "text", "text": "이 음식 사진을 분석해줘."},
            ],
        },
    ]

    # 현재 OpenRouter 무료 비전 모델 (2026-06 기준 실제 동작 확인된 것만)
    _VISION_MODELS = [
        "google/gemma-4-31b-it:free",       # 31B, 가장 정확
        "google/gemma-4-26b-a4b-it:free",   # 26B MoE
        "nvidia/nemotron-nano-12b-v2-vl:free",  # 소형 폴백
    ]

    def _call(model_id: str) -> str:
        resp = client.chat.completions.create(model=model_id, messages=_MESSAGES)
        if resp.choices and resp.choices[0].message.content:
            return resp.choices[0].message.content.strip()
        return ""

    raw = None
    for model_id in _VISION_MODELS:
        # ThreadPoolExecutor로 하드 타임아웃 — 서버가 청크 스트리밍으로
        # keepalive를 보내도 SDK timeout을 우회하는 문제 방지
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_call, model_id)
            try:
                result = future.result(timeout=_MODEL_TIMEOUT)
                if result:
                    raw = result
                    break
            except (concurrent.futures.TimeoutError, Exception):
                future.cancel()
                continue

    if raw is None:
        raise RuntimeError("모델이 빈 응답을 반환했습니다. 잠시 후 다시 시도해주세요.")

    raw = strip_fence(raw)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        result = {"items": [], "raw_description": raw}

    return result


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("사용법: python step1_recognize.py <이미지_경로>")
        sys.exit(1)
    result = recognize(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))
