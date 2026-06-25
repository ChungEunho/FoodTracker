"""
Lazy-initialised OpenAI client pointing at OpenRouter.

Uses settings.openrouter_api_key exclusively — never os.environ.
The client is a module-level singleton created on first call to get_client().

SECURITY: The API key is loaded from app.config.settings and is NEVER logged,
included in responses, or passed to client code.
"""

from openai import OpenAI

from app.config import settings

_client: OpenAI | None = None


def get_client() -> OpenAI:
    """
    Return the shared OpenAI-compatible client pointed at OpenRouter.

    Initialises the client on first call (lazy init).
    Raises RuntimeError if OPENROUTER_API_KEY is not configured.
    """
    global _client
    if _client is None:
        if not settings.openrouter_api_key:
            raise RuntimeError("OPENROUTER_API_KEY is not configured")
        _client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=settings.openrouter_api_key,
        )
    return _client


def strip_fence(raw: str) -> str:
    """Remove markdown code fence (```) wrapping from a model response."""
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
    return raw
