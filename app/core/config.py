"""
Central configuration for the intelligence service.
Follows GROUND_RULES.md section 12.1 (env vars) — every value here can be
overridden by an environment variable of the same (upper-cased) name.
"""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Identity
    SERVICE_NAME: str = "intelligence"
    MODEL_VERSION: str = "v1.0.0"
    ENV: str = "development"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8003
    LOG_LEVEL: str = "INFO"
    BACKEND_URL: str = "http://localhost:8000"

    # CORS — backend + frontend only talk to this service over private
    # networking in prod, but keep this open for local dev / hackathon demo.
    CORS_ORIGINS: list[str] = ["*"]

    # Neo4j (OPTIONAL per GROUND_RULES 5.2 — "Neo4j (optional)").
    # If NEO4J_URI is unset, GraphStore falls back to an in-memory
    # NetworkX graph so the service runs with zero external dependencies.
    NEO4J_URI: Optional[str] = None
    NEO4J_USER: Optional[str] = None
    NEO4J_PASSWORD: Optional[str] = None

    # Evidence storage. In production this should be Cloudinary/S3 (see
    # GROUND_RULES 3.2). For the hackathon build we default to local disk
    # and expose the same file:// / https:// shaped URL contract so the
    # backend integration does not need to change when storage swaps out.
    EVIDENCE_STORAGE_DIR: str = "/tmp/surakshak360_evidence"
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    # Timeout/retry values are enforced by the CALLER (backend, per
    # GROUND_RULES 4.4: intelligence = 10s timeout, 3 retries). Nothing to
    # configure here, but we keep an internal soft budget for slow ops.
    GRAPH_QUERY_SOFT_BUDGET_MS: int = 3000


@lru_cache
def get_settings() -> Settings:
    return Settings()
