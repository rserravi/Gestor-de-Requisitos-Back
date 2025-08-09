# app/api/endpoints/state_machine.py

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from datetime import datetime
from typing import Optional, Dict, Any, List

from app.database import get_session
from app.api.endpoints.auth import get_current_user
from app.models.user import User
from app.models.state_machine import StateMachine
from app.schemas.state_machine import StateMachineRead, StateMachineUpdate
from app.models.chat_message import ChatMessage
from app.models.requirement import Requirement

from app.utils.prompt_loader import load_prompt
from app.utils.ollama_client import call_ollama

from app.utils.analyze_parser import parse_analyze_output
from app.utils.message_loader import load_message  


router = APIRouter()


@router.get("/project/{project_id}", response_model=StateMachineRead)
def get_state_machine(
    project_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    state_machine = session.exec(
        select(StateMachine)
        .where(StateMachine.project_id == project_id)
        .order_by(StateMachine.last_updated.desc())
    ).first()
    if not state_machine:
        raise HTTPException(status_code=404, detail="StateMachine not found")
    return state_machine


@router.post("/project/{project_id}", response_model=StateMachineRead)
def post_state_machine(
    project_id: int,
    update: StateMachineUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    - Si state == 'analyze_requisites':
        * Construye contexto (descripción + requisitos actuales)
        * Llama a IA con prompt analyze_requisites.txt
        * Guarda preguntas en StateMachine.extra (questions/current/answers)
        * Inserta ChatMessage con la primera pregunta (sender='ai', state='analyze_requisites')
        * Devuelve el nuevo StateMachine
    - En otros casos, sólo registra entrada histórica con el 'state' y 'extra' recibidos.
    """
    if update.state == "analyze_requisites":
        # 1) DESCRIPCIÓN ORIGINAL (primer user msg en estado 'init')
        desc_msg = session.exec(
            select(ChatMessage)
            .where(ChatMessage.project_id == project_id)
            .where(ChatMessage.sender == "user")
            .where(ChatMessage.state == "init")
            .order_by(ChatMessage.timestamp)
        ).first()
        descripcion_usuario = desc_msg.content if desc_msg else ""

        # 2) REQUISITOS ACTUALES (formateados por categoría)
        reqs = session.exec(
            select(Requirement)
            .where(Requirement.project_id == project_id)
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
                lines.append("")  # línea en blanco
            return "\n".join(lines).strip()

        requisitos_actuales = format_requirements(reqs)

        # 3) PROMPT DE ANÁLISIS
        #   Asegúrate de que static/prompts/analyze_requisites.txt acepte
        #   {descripcion_usuario} y {requisitos_actuales}
        prompt = load_prompt(
            "analyze_requisites.txt",
            descripcion_usuario=descripcion_usuario,
            lista_requisitos=requisitos_actuales,
        )

        # 4) LLAMADA A OLLAMA → lista de preguntas (una por línea)
        questions_txt = call_ollama(prompt)
        questions_list = [q.strip() for q in questions_txt.splitlines() if q.strip()]

        if not questions_list:
            # Si IA no devuelve preguntas, evitamos romper el flujo
            questions_list = ["No se han generado preguntas. Describe cambios que quieras hacer en los requisitos."]

        # 5) CREA ENTRADA HISTÓRICA DE STATE 'analyze_requisites'
        analyze_state = StateMachine(
            project_id=project_id,
            state="analyze_requisites",
            last_updated=datetime.utcnow(),
            extra={
                "mode": "analyze",
                "questions": questions_list,
                "current": 0,
                "answers": [],
            },
        )
        session.add(analyze_state)
        session.commit()
        session.refresh(analyze_state)

        # 6) PUBLICA PRIMERA PREGUNTA EN CHAT (AI)
        first_q = questions_list[0]
        ai_msg = ChatMessage(
            content=first_q,
            sender="ai",
            project_id=project_id,
            state="analyze_requisites",
            timestamp=datetime.utcnow(),
        )
        session.add(ai_msg)
        session.commit()

        return analyze_state

    # --- Fallback genérico: registrar entrada histórica con el estado recibido ---
    new_state = StateMachine(
        project_id=project_id,
        state=update.state,
        last_updated=datetime.utcnow(),
        extra=update.extra or {},
    )
    session.add(new_state)
    session.commit()
    session.refresh(new_state)
    return new_state
