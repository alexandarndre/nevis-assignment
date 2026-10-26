from pydantic import BaseModel


class PostgresSettings(BaseModel):
    DATABASE_URL: str = "postgresql+psycopg://nevis:nevis@localhost:55432/nevis"
