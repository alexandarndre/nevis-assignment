from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProjectSettings(BaseModel):
    PROJECT_NAME: str = "Nevis Search API"
    PROJECT_VERSION: str = "1.0.0"


class EnvironmentSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)
