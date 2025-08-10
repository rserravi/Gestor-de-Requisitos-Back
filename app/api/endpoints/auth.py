from fastapi import APIRouter, HTTPException, status, Depends
from sqlmodel import Session, select
from app.models.user import User
from app.schemas.user import UserCreate, UserRead, Token, UserPreferences, UserUpdate
from app.core.security import verify_password, get_password_hash, create_access_token
from app.database import get_session
from app.core.config import Settings
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from jose import JWTError, jwt
import json
from datetime import datetime

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
settings = Settings()

@router.post("/register", response_model=UserRead)
def register(user_in: UserCreate, session: Session = Depends(get_session)):
    if session.exec(select(User).where(User.username == user_in.username)).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    if session.exec(select(User).where(User.email == user_in.email)).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        username=user_in.username,
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        avatar=user_in.avatar,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    # Devuelve el esquema Pydantic con roles como lista
    return UserRead(
        id=user.id,
        username=user.username,
        email=user.email,
        avatar=user.avatar,
        roles=user.roles.split(",") if user.roles else [],
        last_access_date=user.last_access_date,
        created_date=user.created_date,
        updated_date=user.updated_date,
        active=user.active,
        preferences=UserPreferences()   # <--- Preferencias por defecto, nunca None
    )

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)):
    user = session.exec(select(User).where(User.username == form_data.username)).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    if not user.active:
        raise HTTPException(status_code=403, detail="User inactive")
    token = create_access_token({"sub": str(user.id)})
    return Token(access_token=token)

def get_current_user(token: str = Depends(oauth2_scheme), session: Session = Depends(get_session)):
    credentials_exception = HTTPException(status_code=401, detail="Could not validate credentials")
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = session.get(User, int(user_id))
    if user is None:
        raise credentials_exception
    return user

@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)):
    prefs = current_user.preferences
    if isinstance(prefs, str):
        try:
            prefs = json.loads(prefs)
        except json.JSONDecodeError:
            prefs = {}
    user_prefs = UserPreferences(**prefs) if prefs else UserPreferences()

    return UserRead(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        avatar=current_user.avatar,
        roles=current_user.roles.split(",") if current_user.roles else [],
        last_access_date=current_user.last_access_date,
        created_date=current_user.created_date,
        updated_date=current_user.updated_date,
        active=current_user.active,
        preferences=user_prefs,
    )


@router.put("/me", response_model=UserRead)
def update_me(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if user_update.username is not None:
        current_user.username = user_update.username
    if user_update.email is not None:
        current_user.email = user_update.email
    if user_update.avatar is not None:
        current_user.avatar = user_update.avatar

    current_user.updated_date = datetime.utcnow()
    session.add(current_user)
    session.commit()
    session.refresh(current_user)

    prefs = current_user.preferences
    if isinstance(prefs, str):
        try:
            prefs = json.loads(prefs)
        except json.JSONDecodeError:
            prefs = {}
    user_prefs = UserPreferences(**prefs) if prefs else UserPreferences()

    return UserRead(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        avatar=current_user.avatar,
        roles=current_user.roles.split(",") if current_user.roles else [],
        last_access_date=current_user.last_access_date,
        created_date=current_user.created_date,
        updated_date=current_user.updated_date,
        active=current_user.active,
        preferences=user_prefs,
    )


@router.put("/preferences", response_model=UserPreferences)
def update_preferences(
    preferences: UserPreferences,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    current_user.preferences = preferences.dict()
    current_user.updated_date = datetime.utcnow()
    session.add(current_user)
    session.commit()
    return preferences
