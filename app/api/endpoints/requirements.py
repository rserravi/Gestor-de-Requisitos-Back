# api/endpoints/requirements.py

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func
from typing import List
from app.models.requirement import Requirement
from app.schemas.requirement import (
    RequirementCreate,
    RequirementRead,
    RequirementUpdate,
    RequirementAIGenerateRequest,
)
from app.schemas.chat_message import ChatMessageRead
from app.api.endpoints.auth import get_current_user
from app.database import get_session
from app.models.user import User
from app.models.project import Project
from app.models.state_machine import StateMachine
from app.models.chat_message import ChatMessage
from app.services.context_builder import get_project_description, format_requirements
from app.services.language import resolve_lang, is_es
from app.services.chat_flow import build_example_block
from app.services.requirement_service import parse_requirements_block, append_requirements
from app.utils.prompt_loader import load_prompt
from app.utils.message_loader import load_message
from app.utils.ollama_client import call_ollama

router = APIRouter()

@router.post("/", response_model=RequirementRead, status_code=status.HTTP_201_CREATED)
def create_requirement(
    requirement_in: RequirementCreate,
    project_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # Calcular número correlativo dentro del proyecto
    last_number = session.exec(
        select(func.max(Requirement.number)).where(Requirement.project_id == project_id)
    ).first() or 0
    new_number = last_number + 1

    requirement = Requirement(
        description=requirement_in.description,
        status=requirement_in.status or "draft",
        category=requirement_in.category or "functional",
        priority=requirement_in.priority or "must",
        visual_reference=requirement_in.visual_reference,
        number=new_number,
        project_id=project_id,
        owner_id=current_user.id,
    )
    session.add(requirement)
    session.commit()
    session.refresh(requirement)
    return requirement

@router.get("/project/{project_id}", response_model=List[RequirementRead])
def list_requirements(
    project_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    project = session.get(Project, project_id)
    if not project or project.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Project not found")

    requirements = (
        session.exec(
            select(Requirement)
            .where(Requirement.project_id == project_id)
            .order_by(Requirement.number)
        ).all()
    )
    return requirements


@router.post("/generate", response_model=ChatMessageRead)
def generate_requirements_ai(
    req: RequirementAIGenerateRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    sm = session.exec(
        select(StateMachine)
        .where(StateMachine.project_id == req.project_id)
        .order_by(StateMachine.last_updated.desc())
    ).first()
    if not sm or sm.state != "stall":
        raise HTTPException(status_code=400, detail="State machine not in stall")

    lang = resolve_lang(req.language, sm)
    category = req.category.lower()
    allowed = ["functional", "performance", "usability", "security", "technical"]
    if category not in allowed:
        raise HTTPException(status_code=400, detail="Invalid category")

    desc = get_project_description(session, req.project_id) or ""
    reqs_block = format_requirements(session, req.project_id, lang)
    ejemplo_block = build_example_block(req.example_samples)

    base = load_prompt(
        "add_requisites.txt",
        categoria_upper=category.upper(),
        descripcion_usuario=desc,
        requisitos_actuales=reqs_block,
        ejemplo_requisitos_block=ejemplo_block,
    )
    text = call_ollama(f"Responde SIEMPRE en {lang}.\n\n{base}") or ""
    items = parse_requirements_block(text)
    items = [it for it in items if it["category"] == category]
    append_requirements(session, req.project_id, items, current_user.id)

    cat_es = {
        "functional": "funcionales",
        "performance": "de rendimiento",
        "usability": "de usabilidad",
        "security": "de seguridad",
        "technical": "técnicos",
    }
    cat_en = {
        "functional": "functional",
        "performance": "performance",
        "usability": "usability",
        "security": "security",
        "technical": "technical",
    }
    cat_label = cat_es.get(category, category) if is_es(lang) else cat_en.get(category, category)
    message_file = "add_req_done_es.txt" if is_es(lang) else "add_req_done_en.txt"
    content = load_message(message_file, category=cat_label)

    ai = ChatMessage(
        content=content,
        sender="ai",
        project_id=req.project_id,
        state="stall",
        timestamp=datetime.utcnow(),
    )
    session.add(ai)
    session.commit()
    session.refresh(ai)
    return ai

@router.put("/{requirement_id}", response_model=RequirementRead)
def update_requirement(
    requirement_id: int,
    requirement_in: RequirementUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    req = session.get(Requirement, requirement_id)
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")
    update_data = requirement_in.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(req, key, value)
    req.updated_at = datetime.utcnow()
    session.add(req)
    session.commit()
    session.refresh(req)
    return req

@router.delete("/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_requirement(
    requirement_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    req = session.get(Requirement, requirement_id)
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")
    session.delete(req)
    session.commit()
