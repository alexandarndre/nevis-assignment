from pydantic import BaseModel, Field


class LauncherSettings(BaseModel):
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    WORKERS: int = Field(default=1, ge=1)
    RELOAD: bool = False
