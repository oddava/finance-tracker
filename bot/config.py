from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    BOT_TOKEN: str = Field()

    POSTGRES_USER: str = Field()
    POSTGRES_PASSWORD: str = Field()
    POSTGRES_HOST: str = Field()
    POSTGRES_PORT: int = Field()
    POSTGRES_DB: str = Field()

    OPENAI_API_KEY: str = Field()
    OPENAI_MODEL: str = Field()

    DEBUG: bool = Field()
    TIMEZONE: str = Field()
    DEFAULT_CURRENCY: str = Field()
    DEFAULT_LANGUAGE: str = Field()

    ENABLE_AI_PARSING: bool = Field()
    ENABLE_OCR: bool = Field()
    ENABLE_ANALYTICS: bool = Field()

    RATE_LIMIT_MESSAGES: int = Field()
    RATE_LIMIT_AI_CALLS: int = Field()

    BACKUP_ENABLED: bool = Field()
    BACKUP_PATH: str = Field()

    @property
    def postgresql_url(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def async_postgres_url(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    class Config:
        env_file = "../.env"

settings = Settings()