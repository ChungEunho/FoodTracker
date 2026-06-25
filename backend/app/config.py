"""
Application configuration loaded from environment variables via pydantic-settings.

All secrets and environment-specific values live here.
Never access os.environ directly elsewhere in the codebase — import `settings` instead.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # PostgreSQL connection string for asyncpg.
    # Format: postgresql+asyncpg://user:password@host:port/dbname
    # Example (local dev): postgresql+asyncpg://postgres:postgres@localhost:5432/nutritrack
    # Example (Supabase):  postgresql+asyncpg://postgres:<password>@db.<project>.supabase.co:5432/postgres
    database_url: str

    # Supabase project URL, e.g. https://<project>.supabase.co
    supabase_url: str = ""

    # Supabase service-role key — grants admin-level DB access; NEVER expose to client.
    supabase_service_role_key: str = ""

    # Supabase JWT secret — used to verify tokens issued by Supabase Auth server-side.
    supabase_jwt_secret: str = ""

    # OpenRouter API key for LLM / vision pipeline calls.
    openrouter_api_key: str = ""

    # Optional nutrition search API keys.
    data_go_kr_food_api_key: str = ""
    serpapi_api_key: str = ""
    calorie_ninja_api_key: str = ""

    # Comma-separated allowed CORS origins, e.g. "http://localhost:3000,https://nutritrack.vercel.app"
    # Parsed into a list via allowed_origins_list property — never pass the raw string to CORSMiddleware.
    # Never use "*" with allow_credentials=True.
    allowed_origins: str = "http://localhost:3000"

    # Deployment environment. Defaults to "production" so misconfigured deploys fail safe.
    # Set to "development" in local .env only.
    environment: str = "production"

    # Skip JWT verification for local dev. MUST NOT be true when environment == "production".
    # The server refuses to start if this combination is detected (see main.py lifespan).
    skip_auth: bool = False

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
