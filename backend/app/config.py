"""Application configuration using pydantic-settings."""
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "ModernizationPlatform"
    app_env: str = "development"
    secret_key: str = "change-me-in-production"
    debug: bool = True

    # Backend
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    allowed_origins: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    # Database
    database_url: str = "sqlite+aiosqlite:///./modernization.db"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Worker / Sandbox
    workspace_base_path: str = "/tmp/modernization-workspaces"
    sandbox_enabled: bool = False
    sandbox_docker_image: str = "modernization-worker:latest"
    sandbox_cpu_limit: float = 1.0
    sandbox_memory_limit: str = "2g"
    sandbox_timeout_seconds: int = 600

    # Upload limits
    max_upload_size_mb: int = 100
    max_archive_ratio: int = 50

    # AI / LLM
    llm_provider: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""

    # RAG
    rag_enabled: bool = False

    # Logging
    log_level: str = "INFO"
    audit_log_enabled: bool = True


settings = Settings()
