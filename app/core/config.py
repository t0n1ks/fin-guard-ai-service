import secrets

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

_FALLBACK_KEY = secrets.token_hex(32)


class Settings(BaseSettings):
    brain_api_key: str = ""
    host: str = "0.0.0.0"
    port: int = 8001
    log_level: str = "info"

    @property
    def effective_key(self) -> str:
        k = self.brain_api_key.strip()
        return k if k else _FALLBACK_KEY

    @property
    def maintenance_mode(self) -> bool:
        return not self.brain_api_key.strip()

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
