# create_tables.py
from sqlmodel import SQLModel
from app.database import engine 
import app.models.user 
import app.models.project
import app.models.chat_message
import app.models.state_machine



def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

if __name__ == "__main__":
    create_db_and_tables()
