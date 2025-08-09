from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ChatMessageCreate(BaseModel):
    content: str
    sender: str   # "user" | "ai"
    project_id: int
    state: str    # Uno de los valores StateMachineState
    language: Optional[str] = None  # <-- nuevo (ej: "es", "en", "es-ES")

class ChatMessageRead(BaseModel):
    id: int
    content: str
    sender: str
    timestamp: datetime
    project_id: int
    state: str

    class Config:
        from_attributes = True

class ChatMessageUpdate(BaseModel):
    content: Optional[str] = None
    state: Optional[str] = None
