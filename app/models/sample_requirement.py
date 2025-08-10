from typing import Optional
from sqlmodel import SQLModel, Field


class SampleRequirement(SQLModel, table=True):
    """A single sample requirement line parsed from an uploaded file."""

    id: Optional[int] = Field(default=None, primary_key=True)
    text: str
    file_id: int = Field(foreign_key="samplefile.id")
