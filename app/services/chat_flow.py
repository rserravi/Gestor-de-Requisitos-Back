from datetime import datetime
from typing import Optional, List, Dict
from sqlmodel import Session, select
from app.models.chat_message import ChatMessage
from app.models.state_machine import StateMachine
from app.models.requirement import Requirement
from app.models.user import User
from app.schemas.chat_message import ChatMessageCreate
from app.utils.prompt_loader import load_prompt
from app.utils.message_loader import load_message
from app.utils.ollama_client import call_ollama

from app.services.language import resolve_lang, is_es
from app.services.context_builder import (
    get_project_description,
    format_requirements,
    get_recent_history,
)
from app.services.requirement_service import parse_requirements_block, replace_requirements

# ---------- helper para ejemplo de estilo ----------
def build_example_block(lines: Optional[List[str]]) -> str:
    if not lines:
        return ""
    joined = "\n".join([l for l in lines if str(l).strip()])
    if not joined.strip():
        return ""
    # Bloque etiquetado y encapsulado para el prompt
    return f'\nEJEMPLO DE ESTILO:\n"""\n{joined}\n"""\n'
# ---------------------------------------------------

def handle_init(session: Session, current_user: User, msg: ChatMessageCreate, sm: Optional[StateMachine]):
    lang = resolve_lang(msg.language, sm)
    new_sm = StateMachine(
        project_id=msg.project_id,
        state="software_questions",
        last_updated=datetime.utcnow(),
        extra={"lang": lang},
    )
    session.add(new_sm)
    session.commit()
    session.refresh(new_sm)

    base_prompt = load_prompt("project_questions.txt", descripcion_usuario=msg.content)
    questions_txt = call_ollama(f"Responde SIEMPRE en {lang}.\n\n{base_prompt}")
    questions = [q.strip() for q in (questions_txt or "").splitlines() if q.strip()]
    new_sm.extra = {"lang": lang, "questions": questions, "current": 0, "answers": []}
    session.add(new_sm)
    session.commit()

    session.add(ChatMessage(
        content=msg.content, sender="user",
        project_id=msg.project_id, state="init",
        timestamp=datetime.utcnow(),
    ))

    first_q = questions[0] if questions else ("No se generaron preguntas." if is_es(lang) else "No questions were generated.")
    ai = ChatMessage(
        content=first_q, sender="ai",
        project_id=msg.project_id, state="software_questions",
        timestamp=datetime.utcnow(),
    )
    session.add(ai)
    session.commit()
    session.refresh(ai)
    return ai

def handle_software_questions(session: Session, current_user: User, msg: ChatMessageCreate, sm: StateMachine):
    extra = sm.extra or {}
    lang = extra.get("lang", resolve_lang(msg.language, sm))
    qs = list(extra.get("questions", []))
    idx = int(extra.get("current", 0))
    ans = list(extra.get("answers", []))

    ans.append(msg.content)
    idx += 1

    session.add(ChatMessage(
        content=msg.content, sender="user",
        project_id=msg.project_id, state="software_questions",
        timestamp=datetime.utcnow(),
    ))
    session.commit()

    if idx < len(qs):
        extra.update({"current": idx, "answers": ans, "lang": lang})
        sm.extra = extra
        sm.last_updated = datetime.utcnow()
        session.add(sm)
        session.commit()

        ai = ChatMessage(
            content=qs[idx], sender="ai",
            project_id=msg.project_id, state="software_questions",
            timestamp=datetime.utcnow(),
        )
        session.add(ai)
        session.commit()
        session.refresh(ai)
        return ai

    sm.extra = {"lang": lang, "questions": qs, "answers": ans}
    session.add(sm)
    session.commit()
    return None

def finish_questions_generate_reqs(session: Session, current_user: User, msg: ChatMessageCreate, sm: StateMachine):
    lang = sm.extra.get("lang", "es")
    desc = get_project_description(session, msg.project_id) or ""
    qs = sm.extra.get("questions", [])
    ans = sm.extra.get("answers", [])
    qa_block = "\n".join(f"{q}\n{a}" for q, a in zip(qs, ans))

    # NUEVO: ejemplo de estilo desde el mensaje del usuario (si lo envía)
    ejemplo_estilo_block = build_example_block(msg.example_samples)

    base = load_prompt(
        "generate_new_requisites.txt",
        descripcion_usuario=desc,
        preguntas_y_respuestas=qa_block,
        ejemplo_estilo_block=ejemplo_estilo_block,
    )
    text = call_ollama(f"Responde SIEMPRE en {lang}.\n\n{base}")
    items = parse_requirements_block(text or "")

    replace_requirements(session, msg.project_id, items, current_user.id)

    session.add(StateMachine(
        project_id=msg.project_id, state="new_requisites",
        last_updated=datetime.utcnow(),
        extra={"lang": lang, "questions": qs, "answers": ans},
    ))
    session.commit()

    ai = ChatMessage(
        content=load_message("new_req_end.txt"),
        sender="ai", project_id=msg.project_id,
        state="new_requisites", timestamp=datetime.utcnow(),
    )
    session.add(ai)
    session.commit()
    session.refresh(ai)
    return ai

def handle_analyze_reply(session: Session, current_user: User, msg: ChatMessageCreate, sm: StateMachine):
    analyze_sm = session.exec(
        select(StateMachine)
        .where(StateMachine.project_id == msg.project_id)
        .where(StateMachine.state == "analyze_requisites")
        .order_by(StateMachine.last_updated.desc())
    ).first()
    if not analyze_sm or not analyze_sm.extra:
        raise ValueError("Analyze session not initialized")

    extra: Dict = dict(analyze_sm.extra)
    lang = extra.get("lang", resolve_lang(msg.language, sm))
    questions: List[str] = list(extra.get("questions", []))
    idx: int = int(extra.get("current", 0))
    answers: List[str] = list(extra.get("answers", []))

    # Guarda respuesta del usuario
    session.add(ChatMessage(
        content=msg.content, sender="user",
        project_id=msg.project_id, state="analyze_requisites",
        timestamp=datetime.utcnow(),
    ))
    session.commit()

    answers.append(msg.content)
    idx += 1

    if idx < len(questions):
        extra.update({"answers": answers, "current": idx, "lang": lang})
        analyze_sm.extra = extra
        analyze_sm.last_updated = datetime.utcnow()
        session.add(analyze_sm)
        session.commit()

        ai = ChatMessage(
            content=questions[idx], sender="ai",
            project_id=msg.project_id, state="analyze_requisites",
            timestamp=datetime.utcnow(),
        )
        session.add(ai)
        session.commit()
        session.refresh(ai)
        return ai

    # No quedan preguntas -> mejorar requisitos y pasar a stall
    desc = get_project_description(session, msg.project_id) or ""
    reqs_block = format_requirements(session, msg.project_id, lang)
    qa_block = "\n".join(f"{q}\n{a}" for q, a in zip(questions, answers))

    # NUEVO: ejemplo de estilo desde el mensaje del usuario en esta última respuesta (si lo envía)
    ejemplo_estilo_block = build_example_block(msg.example_samples)

    base = load_prompt(
        "improve_requisites.txt",
        descripcion_usuario=desc,
        preguntas_y_respuestas=qa_block,
        requisitos_actuales=reqs_block,
        ejemplo_estilo_block=ejemplo_estilo_block,
    )
    text = call_ollama(f"Responde SIEMPRE en {lang}.\n\n{base}")
    items = parse_requirements_block(text or "")

    replace_requirements(session, msg.project_id, items, current_user.id)

    session.add(StateMachine(
        project_id=msg.project_id, state="stall",
        last_updated=datetime.utcnow(),
        extra={"from": "analyze_requisites", "answers_count": len(answers), "lang": lang},
    ))
    session.commit()

    final_text = (
        "Análisis completado y requisitos actualizados. Puedes seguir editando y pulsar **Analizar con IA** cuando quieras iterar de nuevo."
        if is_es(lang) else
        "Analysis completed and requirements updated. You can keep editing and press **Analyze with AI** to iterate again."
    )
    ai = ChatMessage(
        content=final_text, sender="ai",
        project_id=msg.project_id, state="stall",
        timestamp=datetime.utcnow(),
    )
    session.add(ai)
    session.commit()
    session.refresh(ai)
    return ai

def handle_stall(session: Session, current_user: User, msg: ChatMessageCreate, sm: StateMachine):
    lang = resolve_lang(msg.language, sm)
    user_msg = ChatMessage(
        content=msg.content, sender="user",
        project_id=msg.project_id, state="stall",
        timestamp=datetime.utcnow(),
    )
    session.add(user_msg)
    session.commit()
    session.refresh(user_msg)

    desc = get_project_description(session, msg.project_id) or ("(sin descripción)" if is_es(lang) else "(no description)")
    reqs_block = format_requirements(session, msg.project_id, lang)
    history = get_recent_history(session, msg.project_id, exclude_id=user_msg.id, limit=14, lang=lang)

    base_prompt = load_prompt(
        "stall_chat.txt",
        lang=lang,
        descripcion_usuario=desc,
        requisitos_actuales=reqs_block,
        historial_chat=history,
        mensaje_usuario=msg.content,
    )
    ai_text = call_ollama(base_prompt) or ""
    ai = ChatMessage(
        content=ai_text.strip(), sender="ai",
        project_id=msg.project_id, state="stall",
        timestamp=datetime.utcnow(),
    )
    session.add(ai)
    session.commit()
    session.refresh(ai)
    return ai

def save_ai_message(session: Session, msg: ChatMessageCreate, state: str):
    ai = ChatMessage(
        content=msg.content, sender="ai",
        project_id=msg.project_id, state=state,
        timestamp=datetime.utcnow(),
    )
    session.add(ai)
    session.commit()
    session.refresh(ai)
    return ai

def save_generic(session: Session, msg: ChatMessageCreate, state: str):
    m = ChatMessage(
        content=msg.content, sender=msg.sender,
        project_id=msg.project_id, state=state,
        timestamp=datetime.utcnow(),
    )
    session.add(m)
    session.commit()
    session.refresh(m)
    return m
