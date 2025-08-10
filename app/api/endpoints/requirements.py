# api/endpoints/requirements.py

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select, func
from typing import List
from app.models.requirement import Requirement
from app.schemas.requirement import RequirementCreate, RequirementRead, RequirementUpdate
from app.api.endpoints.auth import get_current_user
from app.database import get_session
from app.models.user import User
from app.models.project import Project

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
