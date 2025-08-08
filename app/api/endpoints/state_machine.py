from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from datetime import datetime
from app.models.state_machine import StateMachine
from app.schemas.state_machine import StateMachineRead, StateMachineUpdate
from app.api.endpoints.auth import get_current_user
from app.database import get_session
from app.models.user import User

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
def add_state_machine_entry(
    project_id: int,
    update: StateMachineUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    # Crea nueva entrada con el estado y extra
    state_machine = StateMachine(
        project_id=project_id,
        state=update.state,
        last_updated=datetime.utcnow(),
        extra=update.extra or {}
    )
    session.add(state_machine)
    session.commit()
    session.refresh(state_machine)
    return state_machine
