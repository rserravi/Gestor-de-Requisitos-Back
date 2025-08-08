from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from app.models.chat_message import ChatMessage
from app.schemas.chat_message import ChatMessageCreate, ChatMessageRead, ChatMessageUpdate
from app.api.endpoints.auth import get_current_user
from app.database import get_session
from app.models.user import User

router = APIRouter()

@router.post("/", response_model=ChatMessageRead)
def create_message(
    message_in: ChatMessageCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # (Opcional: podrías validar que el usuario tiene acceso a project_id)
    msg = ChatMessage(**message_in.dict())
    session.add(msg)
    session.commit()
    session.refresh(msg)
    return msg

@router.get("/project/{project_id}", response_model=List[ChatMessageRead])
def get_project_messages(
    project_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # (Opcional: validación de acceso a project)
    messages = session.exec(
        select(ChatMessage)
        .where(ChatMessage.project_id == project_id)
        .order_by(ChatMessage.timestamp)
    ).all()
    return messages

@router.delete("/{message_id}", status_code=204)
def delete_message(
    message_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    msg = session.get(ChatMessage, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    # (Opcional: solo permitir borrar mensajes del user o admins)
    session.delete(msg)
    session.commit()

@router.put("/{message_id}", response_model=ChatMessageRead)
def update_message(
    message_id: int,
    message_in: ChatMessageUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    msg = session.get(ChatMessage, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    # Opcional: permitir solo si msg.sender == "user" y pertenece al current_user
    update_data = message_in.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(msg, key, value)
    session.add(msg)
    session.commit()
    session.refresh(msg)
    return msg