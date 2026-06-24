from client import client

# ── 1. 텍스트 인식 테스트 (openai/gpt-oss-120b:free) ──────────────────────────
print("=" * 60)
print("[텍스트] openai/gpt-oss-120b:free")
print("=" * 60)

text_response = client.chat.completions.create(
    model="openai/gpt-oss-120b:free",
    messages=[
        {"role": "user", "content": "What is the capital of South Korea? Answer in one sentence."}
    ],
)
print("응답:", text_response.choices[0].message.content)
print("토큰 사용:", text_response.usage)

# ── 2. 이미지 인식 테스트 (google/gemma-4-31b-it:free) ────────────────────────
print()
print("=" * 60)
print("[이미지] google/gemma-4-31b-it:free")
print("=" * 60)

import base64

image_path = "/tmp/test_image.jpg"
with open(image_path, "rb") as f:
    image_data = base64.standard_b64encode(f.read()).decode("utf-8")
data_url = f"data:image/jpeg;base64,{image_data}"

image_response = client.chat.completions.create(
    model="google/gemma-4-31b-it:free",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_url}},
                {"type": "text", "text": "What is in this image? Describe briefly."},
            ],
        }
    ],
)
print("이미지: /tmp/test_image.jpg (base64 전송)")
print("응답:", image_response.choices[0].message.content)
print("토큰 사용:", image_response.usage)
