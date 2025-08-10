import sys
import os
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("database_url", "sqlite:///:memory:")

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool

from app.main import app
from app.api.endpoints.auth import get_current_user
from app.database import get_session
from app.models.user import User
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.state_machine import StateMachine
from app.models.chat_message import ChatMessage

import app.api.endpoints.requirements as req_api


def create_test_client():
    app.dependency_overrides.clear()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as session:
            yield session

    client = TestClient(app)
    user = User(id=1, username="alice", email="alice@example.com", password_hash="hashed")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = override_get_session

    with Session(engine) as session:
        session.add(user)
        session.commit()
        session.refresh(user)

    return client, engine


def patch_ai_helpers():
    req_api.call_ollama = lambda prompt: ""
    req_api.parse_requirements_block = lambda text: [
        {
            "description": "Req AI",
            "status": "draft",
            "priority": "must",
            "category": "functional",
            "visual_reference": None,
        }
    ]
    req_api.append_requirements = lambda session, project_id, items, owner_id: None
    req_api.get_project_description = lambda session, project_id: ""
    req_api.format_requirements = lambda session, project_id, lang: ""
    req_api.build_example_block = lambda samples: ""
    req_api.load_prompt = lambda filename, **kwargs: ""
    req_api.load_message = lambda filename, **kwargs: "ok"
    req_api.resolve_lang = lambda language, sm: language or "es"


def test_create_requirement_sequential_number():
    client, engine = create_test_client()
    with Session(engine) as session:
        project = Project(id=1, name="P1", description="desc", owner_id=1)
        session.add(project)
        session.commit()

    r1 = client.post("/requirements/?project_id=1", json={"description": "Req 1"})
    assert r1.status_code == 201
    assert r1.json()["number"] == 1

    r2 = client.post("/requirements/?project_id=1", json={"description": "Req 2"})
    assert r2.status_code == 201
    assert r2.json()["number"] == 2

    app.dependency_overrides.clear()


def test_list_requirements_project_validation():
    client, engine = create_test_client()
    with Session(engine) as session:
        project1 = Project(id=1, name="P1", description="d1", owner_id=1)
        req = Requirement(
            id=1,
            description="R1",
            status="draft",
            category="functional",
            priority="must",
            visual_reference=None,
            number=1,
            project_id=1,
            owner_id=1,
        )
        user2 = User(id=2, username="bob", email="bob@example.com", password_hash="hashed")
        project2 = Project(id=2, name="P2", description="d2", owner_id=2)
        session.add(project1)
        session.add(req)
        session.add(user2)
        session.add(project2)
        session.commit()

    resp_ok = client.get("/requirements/project/1")
    assert resp_ok.status_code == 200
    assert len(resp_ok.json()) == 1

    resp_fail = client.get("/requirements/project/2")
    assert resp_fail.status_code == 404

    app.dependency_overrides.clear()


def test_generate_requirements_ai_valid():
    client, engine = create_test_client()
    patch_ai_helpers()
    with Session(engine) as session:
        project = Project(id=1, name="P1", description="d", owner_id=1)
        sm = StateMachine(id=1, project_id=1, state="stall")
        session.add(project)
        session.add(sm)
        session.commit()

    payload = {"project_id": 1, "category": "functional", "language": "es"}
    resp = client.post("/requirements/generate", json=payload)
    assert resp.status_code == 200
    assert resp.json()["sender"] == "ai"

    app.dependency_overrides.clear()


def test_generate_requirements_ai_invalid_category():
    client, engine = create_test_client()
    patch_ai_helpers()
    with Session(engine) as session:
        project = Project(id=1, name="P1", description="d", owner_id=1)
        sm = StateMachine(id=1, project_id=1, state="stall")
        session.add(project)
        session.add(sm)
        session.commit()

    payload = {"project_id": 1, "category": "unknown"}
    resp = client.post("/requirements/generate", json=payload)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid category"

    app.dependency_overrides.clear()


def test_generate_requirements_ai_state_machine_not_stall():
    client, engine = create_test_client()
    patch_ai_helpers()
    with Session(engine) as session:
        project = Project(id=1, name="P1", description="d", owner_id=1)
        sm = StateMachine(id=1, project_id=1, state="running")
        session.add(project)
        session.add(sm)
        session.commit()

    payload = {"project_id": 1, "category": "functional"}
    resp = client.post("/requirements/generate", json=payload)
    assert resp.status_code == 400
    assert resp.json()["detail"] == "State machine not in stall"

    app.dependency_overrides.clear()


def test_update_delete_nonexistent_requirement():
    client, engine = create_test_client()

    update_resp = client.put("/requirements/999", json={"description": "new"})
    assert update_resp.status_code == 404

    delete_resp = client.delete("/requirements/999")
    assert delete_resp.status_code == 404

    app.dependency_overrides.clear()
