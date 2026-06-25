"""
Food recognition service — port of step1_recognize.py for the FastAPI backend.

Accepts raw image bytes (already read from the upload or downloaded from storage)
instead of a filesystem path.  All path-handling and file-type allow-listing is
removed; the HTTP layer validates the content-type before calling this service.

The three vision models are tried in order with a 30-second hard timeout each,
implemented via ThreadPoolExecutor (same pattern as the original) to prevent the
synchronous OpenAI SDK call from hanging the event loop indefinitely.

The blocking _recognize_sync() function is wrapped in asyncio.run_in_executor so
it never blocks the event loop.
"""

import asyncio
import base64
import concurrent.futures
import io
import json
import logging

from app.services import rate_limiter
from app.services.openrouter_client import get_client, strip_fence

logger = logging.getLogger(__name__)

try:
    from PIL import Image as _PilImage
    _PIL = True
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        pass
except ImportError:
    _PIL = False

_MAX_DIMENSION = 1024       # pixels — match original
_MODEL_TIMEOUT = 30         # seconds per model attempt

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

_VISION_MODELS = [
    "google/gemma-4-31b-it:free",       # 31B, most accurate
    "google/gemma-4-26b-a4b-it:free",   # 26B MoE
    "nvidia/nemotron-nano-12b-v2-vl:free",  # small fallback
]


def _bytes_to_data_url(data: bytes) -> str:
    """
    Convert raw image bytes to a standard JPEG data URL.

    If PIL is available, the image is opened, optionally resized to _MAX_DIMENSION,
    and re-encoded as JPEG (normalises exotic formats, HEIC, non-standard JPEG, etc.).
    Without PIL, the raw bytes are base64-encoded as-is with image/jpeg mime type.
    """
    if _PIL:
        img = _PilImage.open(io.BytesIO(data)).convert("RGB")
        if max(img.size) > _MAX_DIMENSION:
            img.thumbnail((_MAX_DIMENSION, _MAX_DIMENSION), _PilImage.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        encoded = base64.standard_b64encode(buf.getvalue()).decode()
        return f"data:image/jpeg;base64,{encoded}"

    encoded = base64.standard_b64encode(data).decode()
    return f"data:image/jpeg;base64,{encoded}"


def _recognize_sync(image_bytes: bytes) -> dict:
    """
    Blocking synchronous recognition logic (runs in a thread executor).

    Tries each vision model in order with a hard 30-second timeout.
    Returns a dict with keys: items (list), raw_description (str).
    Raises RuntimeError if all models return empty responses.
    """
    data_url = _bytes_to_data_url(image_bytes)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_url}},
                {"type": "text", "text": "이 음식 사진을 분석해줘."},
            ],
        },
    ]

    def _call(model_id: str) -> str:
        c = get_client()
        resp = c.chat.completions.create(model=model_id, messages=messages)
        if resp.choices and resp.choices[0].message.content:
            return resp.choices[0].message.content.strip()
        return ""

    raw = None
    for model_id in _VISION_MODELS:
        # Hard per-model timeout via ThreadPoolExecutor — prevents SDK-level
        # keepalive streams from bypassing the timeout.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(_call, model_id)
            try:
                result = future.result(timeout=_MODEL_TIMEOUT)
                if result:
                    raw = result
                    break
            except (concurrent.futures.TimeoutError, Exception) as exc:
                logger.warning(
                    "Vision model %s failed or timed out: %s",
                    model_id,
                    type(exc).__name__,
                )
                future.cancel()
                continue

    if raw is None:
        raise RuntimeError(
            "모든 비전 모델이 응답하지 않았습니다. 잠시 후 다시 시도해주세요."
        )

    raw = strip_fence(raw)

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"items": [], "raw_description": raw}


async def recognize(image_bytes: bytes) -> dict:
    """
    Async wrapper: runs _recognize_sync in a thread executor.

    Consumes one rate-limit slot per model attempt would be ideal, but because
    the sync loop handles model fallback internally, we consume one slot here
    before the call block (conservative — counts the entire recognition attempt
    as one slot against the daily limit).

    Args:
        image_bytes: Raw bytes of the uploaded image.

    Returns:
        dict with keys: items (list of food item dicts), raw_description (str).

    Raises:
        RateLimitError: if the daily OpenRouter quota is exhausted.
        RuntimeError:   if all vision models fail.
    """
    await rate_limiter.consume()

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _recognize_sync, image_bytes)
