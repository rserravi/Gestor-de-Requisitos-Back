from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from app.models.chat_message import ChatMessage
from app.schemas.chat_message import ChatMessageCreate, ChatMessageRead, ChatMessageUpdate
from app.api.endpoints.auth import get_current_user
from app.database import get_session
from app.models.user import User
from app.models.state_machine import StateMachine
from app.schemas.state_machine import StateMachineUpdate
from datetime import datetime

from app.utils.ollama_client import call_ollama
from app.utils.prompt_loader import load_prompt

router = APIRouter()

@router.post("/", response_model=ChatMessageRead)
def create_message(
    message_in: ChatMessageCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # 1. Recupera el estado actual del proyecto (última entrada)
    state_machine = session.exec(
        select(StateMachine)
        .where(StateMachine.project_id == message_in.project_id)
        .order_by(StateMachine.last_updated.desc())
    ).first()
    current_state = state_machine.state if state_machine else "init"

    # --- Lógica para mensajes del usuario ---
    if message_in.sender == "user":
        if current_state == "init":
            # a. Avanza a software_questions
            new_state = StateMachine(
                project_id=message_in.project_id,
                state="software_questions",
                last_updated=datetime.utcnow(),
                extra={}
            )
            session.add(new_state)
            session.commit()
            session.refresh(new_state)

            # b. Llama a la IA para obtener preguntas
            prompt = load_prompt("project_questions.txt", descripcion_usuario=message_in.content)
            questions_txt = call_ollama(prompt)
            questions_list = [q.strip() for q in questions_txt.splitlines() if q.strip()]

            # c. Guarda en extra
            new_state.extra = {"questions": questions_list, "current": 0, "answers": []}
            session.add(new_state)
            session.commit()

            # d. Guarda el mensaje de descripción user (para el historial)
            user_msg = ChatMessage(
                content=message_in.content,
                sender="user",
                project_id=message_in.project_id,
                state="init",
                timestamp=datetime.utcnow(),
            )
            session.add(user_msg)

            # e. Crea y devuelve el primer mensaje AI (pregunta 1)
            first_question = questions_list[0] if questions_list else "No se generaron preguntas."
            ai_msg = ChatMessage(
                content=first_question,
                sender="ai",
                project_id=message_in.project_id,
                state="software_questions",
                timestamp=datetime.utcnow(),
            )
            session.add(ai_msg)
            session.commit()
            session.refresh(ai_msg)
            return ai_msg

        elif current_state == "software_questions":
            # a. Recupera preguntas y respuestas actuales
            extra = state_machine.extra or {}
            questions = extra.get("questions", [])
            q_idx = extra.get("current", 0)
            answers = extra.get("answers", [])

            # b. Guarda la respuesta
            answers.append(message_in.content)
            q_idx += 1

            # c. Guarda el mensaje del user (respuesta a la pregunta)
            user_msg = ChatMessage(
                content=message_in.content,
                sender="user",
                project_id=message_in.project_id,
                state="software_questions",
                timestamp=datetime.utcnow(),
            )
            session.add(user_msg)
            session.commit()
            session.refresh(user_msg)

            # d. ¿Hay más preguntas?
            if q_idx < len(questions):
                extra["current"] = q_idx
                extra["answers"] = answers
                state_machine.extra = extra
                state_machine.last_updated = datetime.utcnow()
                session.add(state_machine)
                session.commit()

                # Siguiente pregunta
                next_question = questions[q_idx]
                ai_msg = ChatMessage(
                    content=next_question,
                    sender="ai",
                    project_id=message_in.project_id,
                    state="software_questions",
                    timestamp=datetime.utcnow(),
                )
                session.add(ai_msg)
                session.commit()
                session.refresh(ai_msg)
                return ai_msg
            else:
                # Todas respondidas: Avanza a new_requisites
                new_state = StateMachine(
                    project_id=message_in.project_id,
                    state="new_requisites",
                    last_updated=datetime.utcnow(),
                    extra={"questions": questions, "answers": answers}
                )
                session.add(new_state)
                session.commit()

                # Mensaje final opcional (puedes cambiarlo)
                final_msg = ChatMessage(
                    content="¡Gracias! Ya tengo toda la información. Generaré los requisitos.",
                    sender="ai",
                    project_id=message_in.project_id,
                    state="new_requisites",
                    timestamp=datetime.utcnow(),
                )
                session.add(final_msg)
                session.commit()
                session.refresh(final_msg)
                return final_msg

    # --- Mensajes IA siempre usan el estado global actual ---
    elif message_in.sender == "ai":
        used_state = current_state
        ai_msg = ChatMessage(
            content=message_in.content,
            sender="ai",
            project_id=message_in.project_id,
            state=used_state,
            timestamp=datetime.utcnow(),
        )
        session.add(ai_msg)
        session.commit()
        session.refresh(ai_msg)
        return ai_msg

    # --- Mensajes user en otros estados, o fallback: solo guardar ---
    else:
        msg = ChatMessage(
            content=message_in.content,
            sender=message_in.sender,
            project_id=message_in.project_id,
            state=current_state,
            timestamp=datetime.utcnow(),
        )
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