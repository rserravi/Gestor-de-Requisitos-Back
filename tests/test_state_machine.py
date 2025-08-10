import sys
import os
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("database_url", "sqlite:///:memory:")

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine, select
from sqlalchemy.pool import StaticPool
from unittest.mock import patch

from app.main import app
from app.models.user import User
from app.models.project import Project
from app.models.requirement import Requirement
from app.models.state_machine import StateMachine
from app.models.chat_message import ChatMessage
from app.api.endpoints.auth import get_current_user
from app.database import get_session


def create_engine_and_tables():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def test_get_state_machine_success():
    engine = create_engine_and_tables()
    with Session(engine) as session:
        user = User(id=1, username="alice", email="a@example.com", password_hash="hashed")
        project = Project(id=1, name="Proj", description="Desc", owner_id=1)
        sm = StateMachine(project_id=1, state="init", extra={"lang": "es"})
        session.add(user)
        session.add(project)
        session.add(sm)
        session.commit()

    def override_get_session():
        with Session(engine) as session:
            yield session

    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = override_get_session

    response = client.get("/state_machine/project/1")
    assert response.status_code == 200
    assert response.json()["state"] == "init"

    app.dependency_overrides.clear()


def test_get_state_machine_not_found():
    engine = create_engine_and_tables()
    with Session(engine) as session:
        user = User(id=1, username="alice", email="a@example.com", password_hash="hashed")
        project = Project(id=1, name="Proj", description="Desc", owner_id=1)
        session.add(user)
        session.add(project)
        session.commit()

    def override_get_session():
        with Session(engine) as session:
            yield session

    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = override_get_session

    response = client.get("/state_machine/project/1")
    assert response.status_code == 404

    app.dependency_overrides.clear()


def test_post_state_machine_analyze_requisites():
    engine = create_engine_and_tables()
    with Session(engine) as session:
        user = User(id=1, username="alice", email="a@example.com", password_hash="hashed")
        project = Project(id=1, name="Proj", description="Desc", owner_id=1)
        req1 = Requirement(description="Req 1", number=1, project_id=1, owner_id=1)
        req2 = Requirement(description="Req 2", category="performance", number=2, project_id=1, owner_id=1)
        sm_prev = StateMachine(project_id=1, state="init", extra={"lang": "es"})
        session.add(user)
        session.add(project)
        session.add(req1)
        session.add(req2)
        session.add(sm_prev)
        session.commit()

    def override_get_session():
        with Session(engine) as session:
            yield session

    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = override_get_session

    fake_response = (
        "COMENTARIOS:\n1. Comentario.\n\nPREGUNTAS:\n1. Primera?\n2. Segunda?"
    )

    def fake_call_ollama(prompt: str, model: str = "llama3:8b", settings=None) -> str:
        return fake_response

    def fake_load_prompt(filename: str, **kwargs):
        return "prompt"

    with patch("app.api.endpoints.state_machine.call_ollama", fake_call_ollama), \
         patch("app.api.endpoints.state_machine.load_prompt", fake_load_prompt):
        response = client.post("/state_machine/project/1", json={"state": "analyze_requisites"})

    assert response.status_code == 200
    data = response.json()
    assert data["state"] == "analyze_requisites"
    assert data["extra"]["questions"] == ["Primera?", "Segunda?"]
    assert data["extra"]["lang"] == "es"

    with Session(engine) as session:
        messages = session.exec(select(ChatMessage).where(ChatMessage.project_id == 1)).all()
        contents = [m.content for m in messages]
        assert len(contents) == 2
        assert "Comentario." in contents
        assert "Primera?" in contents

    app.dependency_overrides.clear()


def test_post_state_machine_generic_lang_persisted():
    engine = create_engine_and_tables()
    with Session(engine) as session:
        user = User(id=1, username="alice", email="a@example.com", password_hash="hashed")
        project = Project(id=1, name="Proj", description="Desc", owner_id=1)
        sm_prev = StateMachine(project_id=1, state="init", extra={"lang": "fr"})
        session.add(user)
        session.add(project)
        session.add(sm_prev)
        session.commit()

    def override_get_session():
        with Session(engine) as session:
            yield session

    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = override_get_session

    response = client.post(
        "/state_machine/project/1",
        json={"state": "stall", "extra": {"foo": "bar"}},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["extra"]["foo"] == "bar"
    assert data["extra"]["lang"] == "fr"

    app.dependency_overrides.clear()
