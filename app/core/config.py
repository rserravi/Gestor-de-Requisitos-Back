from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    secret_key: str
    database_url: str
    backend_cors_origins: str = "http://localhost:5173"
    ollama_url: str = "http://localhost:11434"
    sql_echo: bool = False

    class Config:
        env_file = ".env"
        extra = "allow"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]
