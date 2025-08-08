from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field, Column
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSON

class StateMachine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="project.id", index=True)  # sin unique!
    state: str
    last_updated: datetime = Field(default_factory=datetime.utcnow)
    extra: Optional[Dict[str, Any]] = Field(default_factory=dict, sa_column=Column(JSON))
