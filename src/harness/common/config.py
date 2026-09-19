from functools import lru_cache
from pathlib import Path

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    query_api_host: str = "0.0.0.0"
    query_api_port: int = 8000

    indexing_api_host: str = "0.0.0.0"
    indexing_api_port: int = 8001

    llm_server_url: HttpUrl = Field(
        default="http://127.0.0.1:8080"
    )
    llm_api_key: str = "no-key"
    llm_model: str = "qwen3-coder-next"

    llm_timeout_seconds: float = 600.0
    llm_max_tokens: int = 2048
    llm_temperature: float = 0.1

    # Общие данные indexing/query сервисов.
    repository_data_root: Path = Path(
        "/home/code-rag-data"
    )

    # Разрешённая область для local repositories.
    repository_local_root: Path = Path(
        "/home/code"
    )

    @property
    def llm_openai_base_url(self) -> str:
        return (
            f"{str(self.llm_server_url).rstrip('/')}/v1"
        )

    @property
    def llm_health_url(self) -> str:
        return (
            f"{str(self.llm_server_url).rstrip('/')}/health"
        )

    @property
    def repository_registry_path(self) -> Path:
        return (
            self.repository_data_root
            / "repositories.json"
        )

    @property
    def repository_storage_root(self) -> Path:
        return (
            self.repository_data_root
            / "repos"
        )

    @property
    def revision_registry_path(self) -> Path:
        return (
            self.repository_data_root
            / "revisions.json"
        )

    @property
    def repository_mirror_root(self) -> Path:
        return self.repository_data_root / "mirrors"

    @property
    def revision_materialization_root(self) -> Path:
        return self.repository_data_root / "materialized"

@lru_cache
def get_settings() -> Settings:
    return Settings()
