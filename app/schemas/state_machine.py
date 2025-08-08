from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class StateMachineRead(BaseModel):
    id: int
    project_id: int
    state: str
    last_updated: datetime
    extra: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True

class StateMachineUpdate(BaseModel):
    state: str
    extra: Optional[Dict[str, Any]] = None
