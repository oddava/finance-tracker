from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str = Field()
    ADMIN_IDS: list[int] = []

    POSTGRES_USER: str = Field()
    POSTGRES_PASSWORD: str = Field()
    POSTGRES_HOST: str = Field()
    POSTGRES_PORT: int = Field()
    POSTGRES_DB: str = Field()

    OPENAI_API_KEY: str = Field()
    OPENAI_MODEL: str = Field()

    DEBUG: bool = Field()
    ENVIRONMENT: str = Field()
    ENABLE_LOGS: str = Field()
    MAINTENANCE_MODE: bool = False
    MAINTENANCE_MESSAGE: str = (
        "🔧 <b>Bot is under maintenance</b>\n\n"
        "We're currently performing updates to improve your experience.\n"
        "Please try again in a few minutes.\n\n"
        "Thank you for your patience! 🙏"
    )
    ENABLE_AI_PARSING: bool = Field()
    ENABLE_OCR: bool = Field()
    ENABLE_ANALYTICS: bool = Field()

    USE_WEBHOOK: bool = Field()
    WEBHOOK_URL: str = Field()
    WEBHOOK_PORT: int = Field()
    WEBHOOK_SECRET: str = Field()

    BACKUP_ENABLED: bool = Field()
    BACKUP_PATH: str = Field()

    SENTRY_DSN: str = Field()

    @property
    def postgresql_url(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def async_postgres_url(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    class Config:
        env_file = ".env"


settings = Settings()
