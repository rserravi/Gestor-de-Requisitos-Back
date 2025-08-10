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


def test_upload_and_retrieve_sample_file():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    client = TestClient(app)
    user = User(id=1, username="alice", email="alice@example.com", password_hash="hashed")

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = override_get_session

    content = "Req 1\nReq 2\n"
    response = client.post(
        "/files/upload",
        files={"uploaded_file": ("reqs.txt", content, "text/plain")},
    )
    assert response.status_code == 201
    file_id = response.json()["id"]

    list_resp = client.get("/files/")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    req_resp = client.get(f"/files/{file_id}/requirements")
    assert req_resp.status_code == 200
    assert req_resp.json() == ["Req 1", "Req 2"]

    app.dependency_overrides.clear()


def test_upload_non_txt_file_returns_400():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    client = TestClient(app)
    user = User(id=1, username="alice", email="alice@example.com", password_hash="hashed")

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = override_get_session

    content = "Req 1\nReq 2\n"
    response = client.post(
        "/files/upload",
        files={"uploaded_file": ("reqs.pdf", content, "application/pdf")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Only .txt files are allowed"

    app.dependency_overrides.clear()


def test_upload_file_limit():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    client = TestClient(app)
    user = User(id=1, username="alice", email="alice@example.com", password_hash="hashed")

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = override_get_session

    content = "Req\n"
    for i in range(5):
        response = client.post(
            "/files/upload",
            files={"uploaded_file": (f"reqs{i}.txt", content, "text/plain")},
        )
        assert response.status_code == 201

    response = client.post(
        "/files/upload",
        files={"uploaded_file": ("reqs5.txt", content, "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Maximum number of files reached"

    list_resp = client.get("/files/")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 5

    app.dependency_overrides.clear()
