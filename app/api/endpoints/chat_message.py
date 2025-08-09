from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from app.database import get_session
from app.api.endpoints.auth import get_current_user
from app.models.user import User
from app.models.state_machine import StateMachine
from app.models.chat_message import ChatMessage
from app.schemas.chat_message import ChatMessageCreate, ChatMessageRead, ChatMessageUpdate

from app.services.chat_flow import (
    handle_init,
    handle_software_questions,
    finish_questions_generate_reqs,
    handle_analyze_reply,
    handle_stall,
    save_ai_message,
    save_generic,
)

router = APIRouter()


@router.post("/", response_model=ChatMessageRead)
def create_message(
    message_in: ChatMessageCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    state_machine = session.exec(
        select(StateMachine)
        .where(StateMachine.project_id == message_in.project_id)
        .order_by(StateMachine.last_updated.desc())
    ).first()
    state = state_machine.state if state_machine else "init"

    if message_in.sender == "user" and state == "init":
        return handle_init(session, current_user, message_in, state_machine)

    if message_in.sender == "user" and state == "software_questions":
        progressed = handle_software_questions(session, current_user, message_in, state_machine)
        if progressed is not None:
            return progressed
        return finish_questions_generate_reqs(session, current_user, message_in, state_machine)

    if message_in.sender == "ai":
        return save_ai_message(session, message_in, state)

    if message_in.sender == "user" and state == "analyze_requisites":
        return handle_analyze_reply(session, current_user, message_in, state_machine)

    if message_in.sender == "user" and state == "stall":
        return handle_stall(session, current_user, message_in, state_machine)

    return save_generic(session, message_in, state)


@router.get("/project/{project_id}", response_model=List[ChatMessageRead])
def get_project_messages(
    project_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    messages = session.exec(
        select(ChatMessage)
        .where(ChatMessage.project_id == project_id)
        .order_by(ChatMessage.timestamp)
    ).all()
    return messages


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
    update_data = message_in.dict(exclude_unset=True)
    for k, v in update_data.items():
        setattr(msg, k, v)
    session.add(msg)
    session.commit()
    session.refresh(msg)
    return msg


@router.delete("/{message_id}", status_code=204)
def delete_message(
    message_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    msg = session.get(ChatMessage, message_id)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    session.delete(msg)
    session.commit()
