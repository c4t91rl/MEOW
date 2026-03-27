from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    gemini_api_key: str = ""
    gemini_model: str = "gemma-3-4b-it"
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