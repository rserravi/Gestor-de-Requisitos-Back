from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from app.models.chat_message import ChatMessage
from app.schemas.chat_message import ChatMessageCreate, ChatMessageRead, ChatMessageUpdate
from app.api.endpoints.auth import get_current_user
from app.database import get_session
from app.models.user import User
from app.models.state_machine import StateMachine
from app.models.requirement import Requirement
from app.utils.prompt_loader import load_prompt
from app.utils.message_loader import load_message
from app.utils.ollama_client import call_ollama
from datetime import datetime
import re

router = APIRouter()

@router.post("/", response_model=ChatMessageRead)
def create_message(
    message_in: ChatMessageCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # Recupera el último state_machine
    state_machine = session.exec(
        select(StateMachine)
        .where(StateMachine.project_id == message_in.project_id)
        .order_by(StateMachine.last_updated.desc())
    ).first()
    current_state = state_machine.state if state_machine else "init"

    # --- Caso 1: User envía descripción inicial en "init" ---
    if message_in.sender == "user" and current_state == "init":
        # a. Crea nuevo estado "software_questions"
        new_state = StateMachine(
            project_id=message_in.project_id,
            state="software_questions",
            last_updated=datetime.utcnow(),
            extra={}
        )
        session.add(new_state)
        session.commit()
        session.refresh(new_state)

        # b. Llama a IA para obtener preguntas
        prompt = load_prompt("project_questions.txt", descripcion_usuario=message_in.content)
        questions_txt = call_ollama(prompt)
        questions_list = [q.strip() for q in questions_txt.splitlines() if q.strip()]

        # c. Guarda en extra
        new_state.extra = {"questions": questions_list, "current": 0, "answers": []}
        session.add(new_state)
        session.commit()

        # d. Guarda mensaje user (descripción)
        user_msg = ChatMessage(
            content=message_in.content,
            sender="user",
            project_id=message_in.project_id,
            state="init",
            timestamp=datetime.utcnow(),
        )
        session.add(user_msg)

        # e. Mensaje AI con la primera pregunta
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

    # --- Caso 2: User responde a preguntas en "software_questions" ---
    if message_in.sender == "user" and current_state == "software_questions":
        extra = state_machine.extra or {}
        questions = extra.get("questions", [])
        q_idx = extra.get("current", 0)
        answers = extra.get("answers", [])

        # a. Guarda la respuesta
        answers.append(message_in.content)
        q_idx += 1

        # b. Guarda mensaje user
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

        # c. Si quedan preguntas, pregunta la siguiente
        if q_idx < len(questions):
            extra["current"] = q_idx
            extra["answers"] = answers
            state_machine.extra = extra
            state_machine.last_updated = datetime.utcnow()
            session.add(state_machine)
            session.commit()

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

        # d. Si NO quedan preguntas, avanza a "new_requisites" y genera requisitos
        new_state = StateMachine(
            project_id=message_in.project_id,
            state="new_requisites",
            last_updated=datetime.utcnow(),
            extra={"questions": questions, "answers": answers}
        )
        session.add(new_state)
        session.commit()
        session.refresh(new_state)

        # --- Obtiene descripción original del proyecto ---
        desc_msg = session.exec(
            select(ChatMessage)
            .where(ChatMessage.project_id == message_in.project_id)
            .where(ChatMessage.sender == "user")
            .where(ChatMessage.state == "init")
            .order_by(ChatMessage.timestamp)
        ).first()
        descripcion_usuario = desc_msg.content if desc_msg else ""

        # --- Formatea preguntas y respuestas ---
        preguntas_y_respuestas = "\n".join([f"{q}\n{a}" for q, a in zip(questions, answers)])

        # --- (Opcional) ejemplo_estilo_block, puede ser "" o cargar de archivo ---
        ejemplo_estilo_block = ""

        # --- Llama a IA para generar requisitos ---
        prompt = load_prompt(
            "generate_new_requisites.txt",
            descripcion_usuario=descripcion_usuario,
            preguntas_y_respuestas=preguntas_y_respuestas,
            ejemplo_estilo_block=ejemplo_estilo_block
        )
        requisitos_raw = call_ollama(prompt)

        # --- Parsea los requisitos por categoría ---
        categories = ["FUNCTIONAL", "PERFORMANCE", "USABILITY", "SECURITY", "TECHNICAL"]
        requisito_regex = re.compile(r"^(\w+):\s*$", re.IGNORECASE)
        current_category = None
        req_number = 1
        parsed_reqs = []

        for line in requisitos_raw.splitlines():
            line = line.strip()
            if not line:
                continue
            match = requisito_regex.match(line)
            if match and match.group(1).upper() in categories:
                current_category = match.group(1).lower()
                req_number = 1
                continue
            elif current_category and line.startswith(str(req_number) + "."):
                description = line.split(".", 1)[1].strip()
                parsed_reqs.append({
                    "description": description,
                    "status": "draft",
                    "category": current_category,
                    "priority": "must",
                    "number": req_number,
                })
                req_number += 1

        # --- Guarda los requisitos en la BD ---
        for req in parsed_reqs:
            new_req = Requirement(
                description=req["description"],
                status=req["status"],
                category=req["category"],
                priority=req["priority"],
                visual_reference=None,
                number=req["number"],
                project_id=message_in.project_id,
                owner_id=current_user.id
            )
            session.add(new_req)
        session.commit()

        # --- Mensaje final IA ---
        final_msg = load_message("new_req_end.txt")
        ai_msg = ChatMessage(
            content=final_msg,
            sender="ai",
            project_id=message_in.project_id,
            state="new_requisites",
            timestamp=datetime.utcnow(),
        )
        session.add(ai_msg)
        session.commit()
        session.refresh(ai_msg)
        return ai_msg

    # --- Caso 3: Mensajes IA (se añade en el estado global actual) ---
    if message_in.sender == "ai":
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

    # --- Caso 4: Otros casos, guardar mensaje genérico con estado global ---
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