from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "development"

    # Auth
    jwt_secret: str = "dev-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_expire_min: int = 15
    jwt_refresh_expire_days: int = 7

    # GitHub OAuth login - register an OAuth App at
    # https://github.com/settings/developers with callback URL
    # {github_oauth_redirect_uri}. Login is disabled (503) while client_id/secret
    # are blank. See docs/API.md.
    github_client_id: str = ""
    github_client_secret: str = ""
    github_oauth_redirect_uri: str = "http://localhost:5173/auth/github/callback"

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/structai.db"

    # Model providers
    ollama_base_url: str = "http://localhost:11434"
    ollama_fast_model: str = "qwen2.5:7b-instruct"
    ollama_smart_model: str = "qwen2.5:7b-instruct"

    groq_api_key: str = ""
    groq_fast_model: str = "openai/gpt-oss-20b"
    groq_smart_model: str = "openai/gpt-oss-120b"

    # Optional cost estimation (app/gateway/router.py::estimate_cost_usd) - keyed
    # "{provider}:{model}" -> {"prompt": $ per 1K tokens, "completion": $ per 1K
    # tokens}. No price is ever hardcoded in application logic; an unlisted
    # provider/model (e.g. local Ollama, or simply leaving this unset) costs 0.
    # JSON object via env, e.g.:
    #   TOKEN_PRICE_TABLE={"groq:openai/gpt-oss-20b": {"prompt": 0.0001, "completion": 0.0001}}
    token_price_table: dict[str, dict[str, float]] = Field(default_factory=dict)

    # Shared httpx connection pool (app/core/http_client.py) used by every provider -
    # defaults match httpx's own built-in defaults, just made tunable per deployment.
    http_max_connections: int = 100
    http_max_keepalive_connections: int = 20

    # Structured answers
    structured_max_attempts: int = 3
    structured_timeout_seconds: float = 30.0

    # Guardrails / abuse limits
    rate_limit_per_min: int = 20
    daily_quota_user: int = 30
    # Per-IP, applied to register/login/refresh/github-callback - these take a
    # credential (password or OAuth code) before a user is authenticated, so the
    # per-user limiter above doesn't cover them. Deliberately stricter.
    auth_rate_limit_per_min: int = 10
    pii_mode: Literal["redact", "block"] = "redact"
    email_check_mx: bool = True
    email_check_mx_timeout_seconds: float = 3.0
    email_disposable_domains_file: str = ""

    # Persistence / uploads
    upload_dir: str = "./data/uploads"
    max_upload_size_bytes: int = 10 * 1024 * 1024
    allowed_upload_content_types: str = (
        "text/plain,text/csv,text/markdown,application/json,application/pdf,"
        "image/png,image/jpeg,image/gif,image/webp"
    )

    # Observability
    otel_exporter_otlp_endpoint: str = ""

    # Web / CORS
    cors_origins: str = "http://localhost:5173,http://localhost:8000"

    # MCP server - credentials for the StructAI account the MCP server acts as.
    # Issue these with scripts/mcp_issue_token.py; see docs/MCP_SERVER.md.
    mcp_access_token: str = ""
    mcp_refresh_token: str = ""

    # Build info (GET /health) - normally auto-detected from `git`; set these to
    # override in environments without a .git directory (e.g. a built container).
    git_commit: str = ""
    build_time: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def allowed_upload_content_type_set(self) -> set[str]:
        return {t.strip() for t in self.allowed_upload_content_types.split(",") if t.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
