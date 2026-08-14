"""Application configuration using pydantic-settings with Windows registry fallback."""
import os
import tempfile
import winreg
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve a cross-platform temp workspace root — safely outside the backend directory
_DEFAULT_WORKSPACE = str(Path(tempfile.gettempdir()) / "modernization-workspaces")


def _get_registry_env(name: str) -> str:
    """Safely query Windows User or Machine environment variables from registry."""
    # Check HKEY_CURRENT_USER (User variables)
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            val, _ = winreg.QueryValueEx(key, name)
            return str(val)
    except Exception:
        pass

    # Check HKEY_LOCAL_MACHINE (System variables)
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ) as key:
            val, _ = winreg.QueryValueEx(key, name)
            return str(val)
    except Exception:
        pass

    return ""


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
    workspace_base_path: str = _DEFAULT_WORKSPACE
    sandbox_enabled: bool = False
    sandbox_docker_image: str = "modernization-worker:latest"
    sandbox_cpu_limit: float = 1.0
    sandbox_memory_limit: str = "2g"
    sandbox_timeout_seconds: int = 600

    # Upload limits
    max_upload_size_mb: int = 4096
    max_archive_ratio: int = 50

    # AI / LLM
    llm_provider: str = ""
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"


    # RAG
    rag_enabled: bool = False

    # Logging
    log_level: str = "INFO"
    audit_log_enabled: bool = True

    def __init__(self, **values):
        super().__init__(**values)
        # Registry fallback when stale parent terminal hides environment variables
        if not self.llm_provider:
            self.llm_provider = (
                os.getenv("LLM_PROVIDER")
                or _get_registry_env("LLM_PROVIDER")
                or ""
            )
        if not self.groq_api_key:
            self.groq_api_key = (
                os.getenv("GROQ_API_KEY")
                or _get_registry_env("GROQ_API_KEY")
                or ""
            )
        
        self.validate_llm_settings()

    def validate_llm_settings(self) -> None:
        provider = (self.llm_provider or "").strip().lower()
        if not provider or provider == "none":
            return
        if provider == "groq" and not self.groq_api_key:
            raise ValueError("LLM_PROVIDER is set to 'groq', but GROQ_API_KEY is not configured.")
        if provider == "gemini" and not self.gemini_api_key:
            raise ValueError("LLM_PROVIDER is set to 'gemini', but GEMINI_API_KEY is not configured.")
        if provider == "openai" and not self.openai_api_key:
            raise ValueError("LLM_PROVIDER is set to 'openai', but OPENAI_API_KEY is not configured.")



settings = Settings()
