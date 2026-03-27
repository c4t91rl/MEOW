from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    port: int = 8000
    cache_ttl_seconds: int = 300
    log_level: str = "info"

    # limits
    max_text_length: int = 15000
    max_links: int = 30000
    llm_timeout: int = 20
    domain_check_timeout: int = 6

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()