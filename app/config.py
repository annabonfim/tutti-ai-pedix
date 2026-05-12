"""Application settings loaded from environment variables."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    groq_api_key: str
    groq_model: str = "llama-3.1-70b-versatile"
    java_api_base_url: str
    dotnet_api_base_url: str = "http://localhost:5000"
    app_name: str = "Pedix AI Recommendation Service"
    app_version: str = "1.0.0"


settings = Settings()