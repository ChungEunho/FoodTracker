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

    # 합계 계산
    keys = ("weight_g", "calories_kcal", "carbs_g", "protein_g", "fat_g", "sugar_g")
    total = {k: sum(it.get(k, 0) for it in result.get("items", [])) for k in keys}
    result["total"] = total
    return result


def print_table(result: dict):
    items = result.get("items", [])
    total = result.get("total", {})

    header = f"{'음식':<18} {'중량':>6} {'칼로리':>7} {'탄수':>5} {'단백':>5} {'지방':>5} {'당류':>5}"
    sep = "─" * len(header)
    print(sep)
    print(header)
    print(sep)
    for it in items:
        print(
            f"{it['name']:<18} {it.get('weight_g', 0):>5}g {it.get('calories_kcal', 0):>6}  "
            f"{it.get('carbs_g', 0):>4}g {it.get('protein_g', 0):>4}g "
            f"{it.get('fat_g', 0):>4}g {it.get('sugar_g', 0):>4}g"
        )
    print(sep)
    print(
        f"{'합계':<18} {total.get('weight_g', 0):>5}g {total.get('calories_kcal', 0):>6}  "
        f"{total.get('carbs_g', 0):>4}g {total.get('protein_g', 0):>4}g "
        f"{total.get('fat_g', 0):>4}g {total.get('sugar_g', 0):>4}g"
    )
    print(sep)


if __name__ == "__main__":
    from step1_recognize import recognize

    if len(sys.argv) != 2:
        print("사용법: python step2_nutrition.py <이미지_경로>")
        sys.exit(1)
    step1 = recognize(sys.argv[1])
    result = analyze(step1)
    print_table(result)
    print("\n[JSON 원본]")
    print(json.dumps(result, ensure_ascii=False, indent=2))
