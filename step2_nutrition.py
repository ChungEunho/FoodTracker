import json
import sys
from client import client, strip_fence

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


def analyze(step1_result: dict) -> dict:
    items = step1_result.get("items", [])
    if not items:
        raw = step1_result.get("raw_description", "")
        food_list = raw if raw else "알 수 없는 음식"
    else:
        food_list = "\n".join(
            f"- {it['name']} ({it.get('cooking_method', '')})"
            + (f": {it['notes']}" if it.get("notes") else "")
            for it in items
        )

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b:free",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"다음 음식들의 영양 정보를 분석해줘:\n{food_list}"},
        ],
    )

    raw = response.choices[0].message.content.strip()
    raw = strip_fence(raw)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        return {"items": [], "total": {}, "raw_response": raw}

    keys = ("weight_g", "calories_kcal", "carbs_g", "protein_g", "fat_g", "sugar_g")
    total = {k: sum(it.get(k, 0) for it in result.get("items", [])) for k in keys}
    result["total"] = total
    return result


if __name__ == "__main__":
    from step1_recognize import recognize
    if len(sys.argv) != 2:
        print("사용법: python step2_nutrition.py <이미지_경로>")
        sys.exit(1)
    step1 = recognize(sys.argv[1])
    result = analyze(step1)
    print(json.dumps(result, ensure_ascii=False, indent=2))
