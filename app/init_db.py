from app.models.user import User
from sqlmodel import SQLModel
from app.database import engine

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

if __name__ == "__main__":
    create_db_and_tables()
