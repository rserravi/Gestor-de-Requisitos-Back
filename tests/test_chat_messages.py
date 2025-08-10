import sys
import os
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("database_url", "sqlite:///:memory:")

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.user import User
from app.models.project import Project
from app.models.chat_message import ChatMessage
from app.api.endpoints.auth import get_current_user
from app.database import get_session

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SQLModel.metadata.create_all(engine)


def override_get_session():
    with Session(engine) as session:
        yield session


def setup_db():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


def test_create_generic_message():
    setup_db()
    client = TestClient(app)
    user = User(id=1, username="alice", email="alice@example.com", password_hash="hashed")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = override_get_session

    with Session(engine) as session:
        project = Project(name="Proj", description="Desc", owner_id=user.id)
        session.add(project)
        session.commit()
        session.refresh(project)
        project_id = project.id

    payload = {
        "content": "Hello",
        "sender": "ai",
        "project_id": project_id,
        "state": "init",
    }
    response = client.post("/chat_messages/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["content"] == "Hello"
    assert data["sender"] == "ai"
    assert data["project_id"] == project_id
    assert data["state"] == "init"
    assert "id" in data

    app.dependency_overrides.clear()


def test_list_messages_by_project():
    setup_db()
    client = TestClient(app)
    user = User(id=1, username="alice", email="alice@example.com", password_hash="hashed")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = override_get_session

    with Session(engine) as session:
        p1 = Project(name="P1", description="d1", owner_id=user.id)
        p2 = Project(name="P2", description="d2", owner_id=user.id)
        session.add(p1)
        session.add(p2)
        session.commit()
        session.refresh(p1)
        session.refresh(p2)
        session.add(ChatMessage(content="m1", sender="user", project_id=p1.id, state="init"))
        session.add(ChatMessage(content="m2", sender="ai", project_id=p1.id, state="init"))
        session.add(ChatMessage(content="m3", sender="user", project_id=p2.id, state="init"))
        session.commit()
        p1_id = p1.id

    resp = client.get(f"/chat_messages/project/{p1_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert all(msg["project_id"] == p1_id for msg in data)

    app.dependency_overrides.clear()


def test_update_message_and_404():
    setup_db()
    client = TestClient(app)
    user = User(id=1, username="alice", email="alice@example.com", password_hash="hashed")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = override_get_session

    with Session(engine) as session:
        proj = Project(name="Proj", description="Desc", owner_id=user.id)
        session.add(proj)
        session.commit()
        session.refresh(proj)
        msg = ChatMessage(content="old", sender="user", project_id=proj.id, state="init")
        session.add(msg)
        session.commit()
        session.refresh(msg)
        msg_id = msg.id

    resp = client.put(f"/chat_messages/{msg_id}", json={"content": "updated"})
    assert resp.status_code == 200
    assert resp.json()["content"] == "updated"

    not_found = client.put("/chat_messages/9999", json={"content": "x"})
    assert not_found.status_code == 404

    app.dependency_overrides.clear()


def test_delete_message_and_404():
    setup_db()
    client = TestClient(app)
    user = User(id=1, username="alice", email="alice@example.com", password_hash="hashed")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = override_get_session

    with Session(engine) as session:
        proj = Project(name="Proj", description="Desc", owner_id=user.id)
        session.add(proj)
        session.commit()
        session.refresh(proj)
        msg = ChatMessage(content="bye", sender="user", project_id=proj.id, state="init")
        session.add(msg)
        session.commit()
        session.refresh(msg)
        msg_id = msg.id

    resp = client.delete(f"/chat_messages/{msg_id}")
    assert resp.status_code == 204
    with Session(engine) as session:
        assert session.get(ChatMessage, msg_id) is None

    not_found = client.delete("/chat_messages/9999")
    assert not_found.status_code == 404

    app.dependency_overrides.clear()
