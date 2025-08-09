# app/api/endpoints/state_machine.py

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from datetime import datetime
from typing import Dict, Any, List

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
from app.utils.message_loader import load_message  # por si lo necesitas más adelante

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
        * Construye contexto (requisitos actuales formateados)
        * Llama a IA con prompt analyze_requisites.txt
        * Separa COMENTARIOS y PREGUNTAS con parse_analyze_output
        * Publica COMENTARIOS (si existen) como ChatMessage (sender='ai')
        * Guarda preguntas en StateMachine.extra (questions/current/answers)
        * Inserta ChatMessage con la primera pregunta
        * Devuelve el nuevo StateMachine
    - En otros casos, sólo registra entrada histórica con el 'state' y 'extra' recibidos.
    """
    if update.state == "analyze_requisites":
        # 1) REQUISITOS ACTUALES (formateados por categoría)
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

        lista_requisitos = format_requirements(reqs)

        # 2) PROMPT DE ANÁLISIS
        #   La plantilla debe aceptar {lista_requisitos}
        prompt = load_prompt(
            "analyze_requisites.txt",
            lista_requisitos=lista_requisitos,
        )

        # 3) LLAMADA A OLLAMA → comentarios + preguntas
        raw = call_ollama(prompt)
        comments_text, questions_list = parse_analyze_output(raw)

        # Red de seguridad: por si no hay preguntas
        if not questions_list:
            questions_list = ["No se han generado preguntas específicas. Indica qué te gustaría mejorar en los requisitos."]

        # 4) CREA ENTRADA HISTÓRICA DE STATE 'analyze_requisites'
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

        # 5) PUBLICA COMENTARIOS (si existen) Y LA PRIMERA PREGUNTA
        if comments_text:
            ai_comments = ChatMessage(
                content=comments_text,
                sender="ai",
                project_id=project_id,
                state="analyze_requisites",
                timestamp=datetime.utcnow(),
            )
            session.add(ai_comments)
            session.commit()

        first_q = questions_list[0]
        ai_q = ChatMessage(
            content=first_q,
            sender="ai",
            project_id=project_id,
            state="analyze_requisites",
            timestamp=datetime.utcnow(),
        )
        session.add(ai_q)
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
