from sqlmodel import Session, create_engine
from app.core.config import Settings

settings = Settings()
engine = create_engine(settings.database_url, echo=settings.sql_echo)

def get_session():
    with Session(engine) as session:
        yield session
