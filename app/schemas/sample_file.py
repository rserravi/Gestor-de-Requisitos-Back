from sqlmodel import SQLModel


class SampleFileRead(SQLModel):
    id: int
    filename: str
