from dotenv import load_dotenv
from openai import OpenAI
import os

from _paths import env_path

load_dotenv(env_path())

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)


def strip_fence(raw: str) -> str:
    """마크다운 코드 펜스(```)로 감싸진 응답에서 펜스를 제거한다."""
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
    return raw
