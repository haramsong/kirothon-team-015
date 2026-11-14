import os
from functools import lru_cache

from pydantic import BaseModel


class Settings(BaseModel):
    cors_origins: tuple[str, ...]
    table_name: str


@lru_cache
def get_settings() -> Settings:
    configured_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173")
    origins = tuple(
        origin.strip() for origin in configured_origins.split(",") if origin.strip()
    )
    return Settings(
        cors_origins=origins,
        table_name=os.getenv("TABLE_NAME", "my-own-fridge-inventory"),
    )
