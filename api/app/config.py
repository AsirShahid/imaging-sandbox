from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    orthanc_url: str = "http://orthanc:8042"
    redis_url: str = "redis://redis:6379/0"
    request_timeout: float = 30.0


settings = Settings()
