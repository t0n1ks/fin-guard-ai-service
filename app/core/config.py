from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    brain_api_key: str = "changeme_shared_secret"
    log_level: str = "info"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
