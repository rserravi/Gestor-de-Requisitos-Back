import re
from typing import List, Dict
from sqlmodel import Session, select, func, delete
from app.models.requirement import Requirement

CATS = ["FUNCTIONAL", "PERFORMANCE", "USABILITY", "SECURITY", "TECHNICAL"]
CAT_RE = re.compile(r"^(\w+):\s*$", re.IGNORECASE)

def parse_requirements_block(text: str) -> List[Dict]:
    current = None
    num = 1
    items: List[Dict] = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        m = CAT_RE.match(line)
        if m and m.group(1).upper() in CATS:
            current = m.group(1).lower()
            num = 1
            continue
        if current and (line.startswith(f"{num}.") or line.startswith(f"{num})")):
            if "." in line.split()[0]:
                desc = line.split(".", 1)[1].strip()
            else:
                desc = line.split(")", 1)[1].strip()
            items.append({
                "description": desc,
                "status": "draft",
                "category": current,
                "priority": "must",
                "number": num,
            })
            num += 1
    return items

def replace_requirements(session: Session, project_id: int, parsed_items: List[Dict], owner_id: int):
    """Reemplaza los requisitos de un proyecto de forma atómica."""
    with session.begin():
        session.exec(delete(Requirement).where(Requirement.project_id == project_id))
        for it in parsed_items:
            session.add(
                Requirement(
                    description=it["description"],
                    status=it["status"],
                    category=it["category"],
                    priority=it["priority"],
                    visual_reference=None,
                    number=it["number"],
                    project_id=project_id,
                    owner_id=owner_id,
                )
            )


def append_requirements(session: Session, project_id: int, parsed_items: List[Dict], owner_id: int):
    """Añade nuevos requisitos al proyecto manteniendo los existentes."""
    last_number = (
        session.exec(
            select(func.max(Requirement.number)).where(Requirement.project_id == project_id)
        ).first()
        or 0
    )
    for it in parsed_items:
        last_number += 1
        session.add(
            Requirement(
                description=it["description"],
                status=it["status"],
                category=it["category"],
                priority=it["priority"],
                visual_reference=None,
                number=last_number,
                project_id=project_id,
                owner_id=owner_id,
            )
        )
    session.commit()
