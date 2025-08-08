from sqlmodel import SQLModel, Session, create_engine
from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    database_url: str

    class Config:
        env_file = ".env"
        extra = "allow" 

settings = Settings()
engine = create_engine(settings.database_url, echo=True)

def get_session():
    with Session(engine) as session:
        yield session
