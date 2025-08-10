import sys
import os
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("database_url", "sqlite:///:memory:")

from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine, select
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.user import User
from app.models.project import Project
from app.models.chat_message import ChatMessage
from app.api.endpoints.auth import get_current_user
from app.database import get_session
from app.utils.message_loader import load_message


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SQLModel.metadata.create_all(engine)


def override_get_session():
    with Session(engine) as session:
        yield session


def reset_database():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


def test_create_project_and_initial_messages():
    reset_database()
    client = TestClient(app)
    user = User(id=1, username="alice", email="alice@example.com", password_hash="hashed")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = override_get_session

    payload = {"name": "Proj", "description": "Desc"}
    response = client.post("/projects/", json=payload)
    assert response.status_code == 201
    data = response.json()
    project_id = data["id"]
    assert data["name"] == payload["name"]
    assert data["description"] == payload["description"]

    with Session(engine) as session:
        msgs = (
            session.exec(
                select(ChatMessage)
                .where(ChatMessage.project_id == project_id)
                .order_by(ChatMessage.id)
            ).all()
        )
    assert len(msgs) == 2
    expected1 = load_message(
        "project_welcome_ia1.txt",
        project_name=payload["name"],
        project_description=payload["description"],
    )
    expected2 = load_message("project_welcome_ia2.txt")
    assert msgs[0].sender == "ai" and msgs[0].state == "init" and msgs[0].content == expected1
    assert msgs[1].sender == "ai" and msgs[1].state == "init" and msgs[1].content == expected2

    app.dependency_overrides.clear()


def test_list_projects_filtered_by_owner():
    reset_database()
    client = TestClient(app)
    user = User(id=1, username="alice", email="alice@example.com", password_hash="hashed")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = override_get_session

    with Session(engine) as session:
        session.add(Project(name="mine", description="d1", owner_id=1))
        session.add(Project(name="other", description="d2", owner_id=2))
        session.commit()

    response = client.get("/projects/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "mine"

    app.dependency_overrides.clear()


def test_get_project_by_id_and_404_for_non_owner():
    reset_database()
    client = TestClient(app)
    user = User(id=1, username="alice", email="alice@example.com", password_hash="hashed")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = override_get_session

    with Session(engine) as session:
        own_proj = Project(name="own", description="d", owner_id=1)
        other_proj = Project(name="other", description="d", owner_id=2)
        session.add(own_proj)
        session.add(other_proj)
        session.commit()
        session.refresh(own_proj)
        session.refresh(other_proj)
        own_id = own_proj.id
        other_id = other_proj.id

    resp_ok = client.get(f"/projects/{own_id}")
    assert resp_ok.status_code == 200
    assert resp_ok.json()["id"] == own_id

    resp_404 = client.get(f"/projects/{other_id}")
    assert resp_404.status_code == 404

    app.dependency_overrides.clear()


def test_update_project_name_and_description():
    reset_database()
    client = TestClient(app)
    user = User(id=1, username="alice", email="alice@example.com", password_hash="hashed")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = override_get_session

    with Session(engine) as session:
        project = Project(name="old", description="old", owner_id=1)
        session.add(project)
        session.commit()
        session.refresh(project)
        pid = project.id

    payload = {"name": "new", "description": "new desc"}
    response = client.put(f"/projects/{pid}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "new"
    assert data["description"] == "new desc"

    with Session(engine) as session:
        updated = session.get(Project, pid)
        assert updated.name == "new"
        assert updated.description == "new desc"

    app.dependency_overrides.clear()


def test_delete_project_and_verify_204_and_404():
    reset_database()
    client = TestClient(app)
    user = User(id=1, username="alice", email="alice@example.com", password_hash="hashed")
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = override_get_session

    with Session(engine) as session:
        project = Project(name="todel", description="d", owner_id=1)
        session.add(project)
        session.commit()
        session.refresh(project)
        pid = project.id

    resp = client.delete(f"/projects/{pid}")
    assert resp.status_code == 204

    resp2 = client.delete(f"/projects/{pid}")
    assert resp2.status_code == 404

    app.dependency_overrides.clear()
