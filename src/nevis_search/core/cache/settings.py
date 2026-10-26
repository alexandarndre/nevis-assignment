from pydantic import BaseModel


class RedisSettings(BaseModel):
    REDIS_URL: str = "redis://localhost:56379/0"
    REDIS_KEY_PREFIX: str = "nevis"
