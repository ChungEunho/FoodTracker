"""
Nutrition analysis service — port of step2_nutrition.py for the FastAPI backend.

Takes the structured step1 recognition result (food item list) and calls the
OpenRouter LLM to estimate weight and macro-nutrients for each item.

The blocking sync call is wrapped in asyncio.run_in_executor so it does not
block the event loop.
"""

import asyncio
import json
import logging

from app.services import rate_limiter
from app.services.openrouter_client import get_client, strip_fence

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a Korean dietitian and nutritionist. Given a list of food items, estimate the weight and macro-nutrients for each item based on Korean Food Safety Ministry (식품안전처) standards.

Output format (JSON only, no markdown):
{
  "items": [
    {
      "name": "음식명",
      "weight_g": 200,
      "calories_kcal": 210,
      "carbs_g": 8,
      "protein_g": 35,
      "fat_g": 4,
      "sugar_g": 3
    }
  ]
}

Rules:
- Estimate a realistic single-serving weight first, then calculate nutrients from that weight
- Base values on Korean Food Safety Ministry database when possible
- All numeric values must be integers
- Output valid JSON only"""


def _analyze_sync(step1_result: dict) -> dict:
    """
    Blocking synchronous nutrition estimation (runs in a thread executor).

    Args:
        step1_result: Output from step1 recognition — must contain 'items' list.

    Returns:
        dict with keys: items (list), total (dict with aggregated macros).
    """
    items = step1_result.get("items", [])
    if not items:
        raw_desc = step1_result.get("raw_description", "")
        food_list = raw_desc if raw_desc else "알 수 없는 음식"
    else:
        food_list = "\n".join(
            f"- {it['name']} ({it.get('cooking_method', '')})"
            + (f": {it['notes']}" if it.get("notes") else "")
            for it in items
        )

    c = get_client()
    response = c.chat.completions.create(
        model="openai/gpt-oss-120b:free",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"다음 음식들의 영양 정보를 분석해줘:\n{food_list}",
            },
        ],
    )

    raw = response.choices[0].message.content.strip()
    raw = strip_fence(raw)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("nutrition_analyze: JSON parse failed, returning empty result")
        return {"items": [], "total": {}, "raw_response": raw}

    # Compute totals — identical to original step2_nutrition.py logic
    keys = ("weight_g", "calories_kcal", "carbs_g", "protein_g", "fat_g", "sugar_g")
    total = {k: sum(it.get(k, 0) for it in result.get("items", [])) for k in keys}
    result["total"] = total
    return result


async def analyze(step1_result: dict) -> dict:
    """
    Async wrapper: runs _analyze_sync in a thread executor.

    Consumes one rate-limit slot before calling the LLM.

    Args:
        step1_result: Output from the recognize service.

    Returns:
        dict with keys: items (list with per-item macros), total (aggregated macros).

    Raises:
        RateLimitError: if the daily OpenRouter quota is exhausted.
    """
    await rate_limiter.consume()

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _analyze_sync, step1_result)
