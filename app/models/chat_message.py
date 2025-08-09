from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime

class ChatMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    content: str
    sender: str  # "user" | "ai"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    project_id: int = Field(foreign_key="project.id", index=True) 
    state: str  # "init" | "software_questions" | "new_requisites" | "analyze_requisites" | "stall"
