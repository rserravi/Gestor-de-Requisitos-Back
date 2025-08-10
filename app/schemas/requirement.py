# schemas/requirement.py

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class RequirementCreate(BaseModel):
    description: str
    status: Optional[str] = "draft"
    category: Optional[str] = "functional"
    priority: Optional[str] = "must"
    visual_reference: Optional[str] = None

class RequirementRead(BaseModel):
    id: int
    description: str
    status: str
    category: str
    priority: str
    visual_reference: Optional[str]
    number: int
    project_id: int
    created_at: datetime
    updated_at: datetime
    owner_id: int

    class Config:
        from_attributes = True

class RequirementUpdate(BaseModel):
    description: Optional[str] = None
    status: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    visual_reference: Optional[str] = None


class RequirementAIGenerateRequest(BaseModel):
    project_id: int
    category: str
    language: Optional[str] = None
    example_samples: Optional[List[str]] = None
