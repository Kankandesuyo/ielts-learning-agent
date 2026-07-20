from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from .env.

    Beginner note:
    - SQLite is enough for this MVP.
    - DATABASE_URL can later become a PostgreSQL URL without changing routers.
    """

    app_name: str = "IELTS Learning Agent"
    environment: str = "development"
    database_url: str = "sqlite:///./ielts_agent.db"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    rag_docs_path: str = "data/ielts_docs"
    knowledge_dir: str = "database"
    knowledge_index_path: str = "data/knowledge_index.json"
    upload_dir: str = "data/uploads"
    max_upload_mb: int = 20
    use_llm: bool = False
    local_dictionary_enabled: bool = True
    local_dictionary_dir: str = "database/legal-dictionaries"
    public_dictionary_fallback: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def rag_docs_dir(self) -> Path:
        return Path(self.rag_docs_path)

    @property
    def upload_path(self) -> Path:
        return Path(self.upload_dir)

    @property
    def knowledge_path(self) -> Path:
        return Path(self.knowledge_dir)

    @property
    def knowledge_index_file(self) -> Path:
        return Path(self.knowledge_index_path)


@lru_cache
def get_settings() -> Settings:
    return Settings()
