from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    database_url: str
    backend_cors_origins: str = "http://localhost:5173"

    class Config:
        env_file = ".env"
        extra = "allow"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]
