from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/knowledge_base"
    nvidia_api_key: str = ""
    nvidia_embed_url: str = "https://integrate.api.nvidia.com/v1/embeddings"
    embed_model: str = "nvidia/llama-3.2-nv-embedqa-1b-v2"
    embed_dimension: int = 2048

    # Table configuration
    table_name: str = "documents"
    content_column: str = "text"
    embedding_column: str = "embedding"
    metadata_column: str = "metadata"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
