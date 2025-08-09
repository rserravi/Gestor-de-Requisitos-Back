from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List, Dict, Optional
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

def resolve_lang(message_lang: Optional[str], state_machine: Optional[StateMachine]) -> str:
    """
    Prioridad:
    1) language recibido en el mensaje
    2) lang guardado previamente en el state_machine.extra
    3) 'es' por defecto
    """
    if message_lang and message_lang.strip():
        return message_lang.strip()
    if state_machine and state_machine.extra and state_machine.extra.get("lang"):
        return str(state_machine.extra.get("lang"))
    return "es"


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
        lang = resolve_lang(message_in.language, state_machine)

        # a. Crea nuevo estado "software_questions"
        new_state = StateMachine(
            project_id=message_in.project_id,
            state="software_questions",
            last_updated=datetime.utcnow(),
            extra={"lang": lang}
        )
        session.add(new_state)
        session.commit()
        session.refresh(new_state)

        # b. Llama a IA para obtener preguntas (forzando idioma)
        base_prompt = load_prompt("project_questions.txt", descripcion_usuario=message_in.content)
        prompt = f"Responde SIEMPRE en {lang}.\n\n{base_prompt}"
        questions_txt = call_ollama(prompt)
        questions_list = [q.strip() for q in questions_txt.splitlines() if q.strip()]

        # c. Guarda en extra
        new_state.extra = {"lang": lang, "questions": questions_list, "current": 0, "answers": []}
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
        first_question = questions_list[0] if questions_list else ("No se generaron preguntas." if lang.startswith("es") else "No questions were generated.")
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
        lang = extra.get("lang", resolve_lang(message_in.language, state_machine))
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
            extra["lang"] = lang
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
            extra={"lang": lang, "questions": questions, "answers": answers}
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

        # --- Llama a IA para generar requisitos (forzando idioma) ---
        base_prompt = load_prompt(
            "generate_new_requisites.txt",
            descripcion_usuario=descripcion_usuario,
            preguntas_y_respuestas=preguntas_y_respuestas,
            ejemplo_estilo_block=ejemplo_estilo_block
        )
        prompt = f"Responde SIEMPRE en {lang}.\n\n{base_prompt}"
        requisitos_raw = call_ollama(prompt)

        # --- Parsea los requisitos por categoría ---
        categories = ["FUNCTIONAL", "PERFORMANCE", "USABILITY", "SECURITY", "TECHNICAL"]
        requisito_header_re = re.compile(r"^(\w+):\s*$", re.IGNORECASE)
        current_category = None
        req_number = 1
        parsed_reqs = []

        for line in requisitos_raw.splitlines():
            line = line.strip()
            if not line:
                continue
            match = requisito_header_re.match(line)
            if match and match.group(1).upper() in categories:
                current_category = match.group(1).lower()
                req_number = 1
                continue
            elif current_category and (line.startswith(f"{req_number}.") or line.startswith(f"{req_number})")):
                # admite "1. " o "1) "
                if "." in line.split()[0]:
                    description = line.split(".", 1)[1].strip()
                else:
                    description = line.split(")", 1)[1].strip()
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

    # --- Caso 4: Usuario contesta preguntas de analyze_requisites ---
    if message_in.sender == "user" and current_state == "analyze_requisites":
        # Recupera la última entrada analyze_requisites
        analyze_sm = session.exec(
            select(StateMachine)
            .where(StateMachine.project_id == message_in.project_id)
            .where(StateMachine.state == "analyze_requisites")
            .order_by(StateMachine.last_updated.desc())
        ).first()

        if not analyze_sm or not analyze_sm.extra:
            raise HTTPException(status_code=400, detail="Analyze session not initialized")

        extra: Dict = dict(analyze_sm.extra)
        lang = extra.get("lang", resolve_lang(message_in.language, state_machine))
        questions: List[str] = list(extra.get("questions", []))
        q_idx: int = int(extra.get("current", 0))
        answers: List[str] = list(extra.get("answers", []))

        # 1) Guarda la respuesta del usuario como mensaje
        user_msg = ChatMessage(
            content=message_in.content,
            sender="user",
            project_id=message_in.project_id,
            state="analyze_requisites",
            timestamp=datetime.utcnow(),
        )
        session.add(user_msg)
        session.commit()
        session.refresh(user_msg)

        # 2) Añade respuesta y avanza índice
        answers.append(message_in.content)
        q_idx += 1

        if q_idx < len(questions):
            # Persistir progreso
            extra["answers"] = answers
            extra["current"] = q_idx
            extra["lang"] = lang
            analyze_sm.extra = extra
            analyze_sm.last_updated = datetime.utcnow()
            session.add(analyze_sm)
            session.commit()

            # Enviar siguiente pregunta
            next_q = questions[q_idx]
            ai_msg = ChatMessage(
                content=next_q,
                sender="ai",
                project_id=message_in.project_id,
                state="analyze_requisites",
                timestamp=datetime.utcnow(),
            )
            session.add(ai_msg)
            session.commit()
            session.refresh(ai_msg)
            return ai_msg

        # ---- Si NO quedan preguntas: mejorar requisitos y pasar a 'stall' ----

        # Descripción original
        desc_msg = session.exec(
            select(ChatMessage)
            .where(ChatMessage.project_id == message_in.project_id)
            .where(ChatMessage.sender == "user")
            .where(ChatMessage.state == "init")
            .order_by(ChatMessage.timestamp)
        ).first()
        descripcion_usuario = desc_msg.content if desc_msg else ""

        # Requisitos actuales (formateados)
        reqs = session.exec(
            select(Requirement)
            .where(Requirement.project_id == message_in.project_id)
            .order_by(Requirement.category, Requirement.number)
        ).all()

        def format_requirements(req_list: List[Requirement]) -> str:
            if not req_list:
                return "Sin requisitos."
            buckets: Dict[str, List[Requirement]] = {}
            for r in req_list:
                buckets.setdefault(r.category.upper(), []).append(r)
            lines: List[str] = []
            for cat in ["FUNCTIONAL", "PERFORMANCE", "USABILITY", "SECURITY", "TECHNICAL"]:
                items = buckets.get(cat, [])
                lines.append(f"{cat}:")
                if items:
                    for r in items:
                        lines.append(f"{r.number}. {r.description}")
                else:
                    lines.append("(sin elementos)")
                lines.append("")
            return "\n".join(lines).strip()

        requisitos_actuales = format_requirements(reqs)
        preguntas_y_respuestas = "\n".join([f"{q}\n{a}" for q, a in zip(questions, answers)])

        # Prompt de mejora (forzando idioma)
        base_prompt = load_prompt(
            "improve_requisites.txt",
            descripcion_usuario=descripcion_usuario,
            preguntas_y_respuestas=preguntas_y_respuestas,
            requisitos_actuales=requisitos_actuales,
            ejemplo_estilo_block="",
        )
        prompt = f"Responde SIEMPRE en {lang}.\n\n{base_prompt}"
        requisitos_raw = call_ollama(prompt)

        # Parseo de requisitos
        categories = ["FUNCTIONAL", "PERFORMANCE", "USABILITY", "SECURITY", "TECHNICAL"]
        requisito_header_re = re.compile(r"^(\w+):\s*$", re.IGNORECASE)
        current_category = None
        req_number = 1
        parsed_reqs = []

        for line in requisitos_raw.splitlines():
            line = line.strip()
            if not line:
                continue
            match = requisito_header_re.match(line)
            if match and match.group(1).upper() in categories:
                current_category = match.group(1).lower()
                req_number = 1
                continue
            elif current_category and (line.startswith(f"{req_number}.") or line.startswith(f"{req_number})")):
                if "." in line.split()[0]:
                    description = line.split(".", 1)[1].strip()
                else:
                    description = line.split(")", 1)[1].strip()
                parsed_reqs.append({
                    "description": description,
                    "status": "draft",
                    "category": current_category,
                    "priority": "must",
                    "number": req_number,
                })
                req_number += 1

        # Política simple: limpiar y reescribir (puedes cambiar a merge)
        for r in reqs:
            session.delete(r)
        session.commit()

        for req in parsed_reqs:
            session.add(Requirement(
                description=req["description"],
                status=req["status"],
                category=req["category"],
                priority=req["priority"],
                visual_reference=None,
                number=req["number"],
                project_id=message_in.project_id,
                owner_id=current_user.id
            ))
        session.commit()

        # Entrada histórica 'stall'
        stall_state = StateMachine(
            project_id=message_in.project_id,
            state="stall",
            last_updated=datetime.utcnow(),
            extra={"from": "analyze_requisites", "answers_count": len(answers), "lang": lang}
        )
        session.add(stall_state)
        session.commit()

        # Mensaje final AI
        final_text = "Análisis completado y requisitos actualizados. Puedes seguir editando y pulsar **Analizar con IA** cuando quieras iterar de nuevo." if lang.startswith("es") else "Analysis completed and requirements updated. You can keep editing and press **Analyze with AI** to iterate again."
        ai_end = ChatMessage(
            content=final_text,
            sender="ai",
            project_id=message_in.project_id,
            state="stall",
            timestamp=datetime.utcnow(),
        )
        session.add(ai_end)
        session.commit()
        session.refresh(ai_end)
        return ai_end

    # --- Caso 5: Otros casos, guardar mensaje genérico con estado global ---
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
    update_data = message_in.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(msg, key, value)
    session.add(msg)
    session.commit()
    session.refresh(msg)
    return msg
