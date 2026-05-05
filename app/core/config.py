from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings

load_dotenv()


class Settings(BaseSettings):
    brain_api_key: str
    host: str = "0.0.0.0"
    port: int = 8001
    log_level: str = "info"

    @field_validator("brain_api_key")
    @classmethod
    def key_must_be_set(cls, v: str) -> str:
        if not v or v.strip() == "":
            raise ValueError("BRAIN_API_KEY must be set in .env or environment — refusing to start")
        return v

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
