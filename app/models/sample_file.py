from typing import Optional
from sqlmodel import SQLModel, Field


class SampleFile(SQLModel, table=True):
    """Represents a text file uploaded by a user containing sample requirements."""

    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str
    owner_id: int = Field(foreign_key="user.id")
