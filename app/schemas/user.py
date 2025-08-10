# schemas/user.py

from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime


class UserPreferences(BaseModel):
    theme: str = "light"
    notifications: bool = True
    language: str = "en"
    timezone: str = "UTC"


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    avatar: Optional[str] = None


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    avatar: Optional[str] = None


class UserRead(BaseModel):
    id: int
    username: str
    email: str
    avatar: Optional[str]
    roles: List[str]
    last_access_date: Optional[datetime]
    created_date: datetime
    updated_date: datetime
    active: bool
    preferences: Optional[UserPreferences] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

