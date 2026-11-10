from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    FLAN_MODEL: str = "google/flan-t5-small"
    FLAN_MAX_NEW_TOKENS: int = 256
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/llm_qa"
    REDIS_URL: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
