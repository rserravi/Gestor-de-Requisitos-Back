from typing import List, Optional
from sqlmodel import SQLModel, Field, Relationship, Column
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSON


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    email: str = Field(unique=True)
    password_hash: str
    avatar: Optional[str] = None
    roles: Optional[str] = ""   # Coma separada, ej: "admin,user"
    last_access_date: Optional[datetime] = None
    created_date: datetime = Field(default_factory=datetime.utcnow)
    updated_date: datetime = Field(default_factory=datetime.utcnow)
    active: bool = True
    preferences: Optional[dict] = Field(default_factory=dict, sa_column=Column(JSON))
    # Notas: projects y exampleFiles se añadirán después como relaciones
