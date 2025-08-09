from typing import List, Dict, Optional
from datetime import datetime
from sqlmodel import Session, select
from app.models.chat_message import ChatMessage
from app.models.requirement import Requirement

def get_project_description(session: Session, project_id: int) -> Optional[str]:
    msg = session.exec(
        select(ChatMessage)
        .where(ChatMessage.project_id == project_id)
        .where(ChatMessage.sender == "user")
        .where(ChatMessage.state == "init")
        .order_by(ChatMessage.timestamp)
    ).first()
    return msg.content if msg else None

def format_requirements(session: Session, project_id: int, lang: str = "es") -> str:
    reqs = session.exec(
        select(Requirement)
        .where(Requirement.project_id == project_id)
        .order_by(Requirement.category, Requirement.number)
    ).all()
    if not reqs:
        return "Sin requisitos." if lang.lower().startswith("es") else "No requirements."

    buckets: Dict[str, List[Requirement]] = {}
    for r in reqs:
        buckets.setdefault(r.category.upper(), []).append(r)

    lines: List[str] = []
    for cat in ["FUNCTIONAL", "PERFORMANCE", "USABILITY", "SECURITY", "TECHNICAL"]:
        items = buckets.get(cat, [])
        lines.append(f"{cat}:")
        if items:
            for r in items:
                lines.append(f"{r.number}. {r.description}")
        else:
            lines.append("(sin elementos)" if lang.lower().startswith("es") else "(empty)")
        lines.append("")
    return "\n".join(lines).strip()

def get_recent_history(
    session: Session,
    project_id: int,
    exclude_id: Optional[int] = None,
    limit: int = 14,
    lang: str = "es",
) -> str:
    q = select(ChatMessage).where(ChatMessage.project_id == project_id).order_by(ChatMessage.timestamp.desc())
    if exclude_id:
        q = q.where(ChatMessage.id != exclude_id)
    rows = session.exec(q.limit(limit)).all()
    rows = list(reversed(rows))

    def who(s: str) -> str:
        if lang.lower().startswith("es"):
            return "Usuario" if s == "user" else "IA"
        return "User" if s == "user" else "AI"

    if not rows:
        return "(sin historial)" if lang.lower().startswith("es") else "(no history)"
    return "\n".join(f"{who(m.sender)}: {m.content}" for m in rows)
