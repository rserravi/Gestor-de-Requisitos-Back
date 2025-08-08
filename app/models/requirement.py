from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime

class Requirement(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    description: str
    status: str = "draft"          # 'draft', 'approved', 'rejected', 'in-review'
    category: str = "functional"   # 'functional', 'performance', 'usability', 'security', 'technical'
    priority: str = "must"         # 'must', 'should', 'could', 'wont'
    visual_reference: Optional[str] = None
    number: int                    # correlativo dentro del proyecto (puedes calcularlo en el backend)
    project_id: int = Field(foreign_key="project.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    owner_id: int = Field(foreign_key="user.id")
