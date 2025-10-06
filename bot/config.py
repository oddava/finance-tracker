from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    BOT_TOKEN: str = Field()

    POSTGRES_USER: str = Field()
    POSTGRES_PASSWORD: str = Field()
    POSTGRES_HOST: str = Field()
    POSTGRES_PORT: int = Field()
    POSTGRES_DB: str = Field()

    class Config:
        env_file = ".env"

settings = Settings()