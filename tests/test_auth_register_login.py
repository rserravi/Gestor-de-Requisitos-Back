import sys
import os
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("database_url", "sqlite:///:memory:")
os.environ.setdefault("secret_key", "testsecret")

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, Session, create_engine
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.user import User
from app.api.endpoints.auth import get_session
from app.core.security import get_password_hash
from app.database import settings as db_settings
from app.api.endpoints import auth as auth_module


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SQLModel.metadata.create_all(engine)


def override_get_session():
    with Session(engine) as session:
        yield session

db_settings.secret_key = "testsecret"
auth_module.settings.secret_key = "testsecret"


@pytest.fixture(autouse=True)
def setup_db():
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


@pytest.fixture
def client():
    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_register_success(client):
    payload = {
        "username": "alice",
        "email": "alice@example.com",
        "password": "secret",
        "avatar": "avatar.png",
    }
    response = client.post("/auth/register", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "alice"
    assert data["email"] == "alice@example.com"
    assert data["id"] is not None


def test_register_duplicate_username_email(client):
    payload = {
        "username": "bob",
        "email": "bob@example.com",
        "password": "secret",
    }
    first = client.post("/auth/register", json=payload)
    assert first.status_code == 200

    response_username = client.post(
        "/auth/register",
        json={"username": "bob", "email": "bob2@example.com", "password": "secret"},
    )
    assert response_username.status_code == 400
    assert response_username.json()["detail"] == "Username already registered"

    response_email = client.post(
        "/auth/register",
        json={"username": "bob2", "email": "bob@example.com", "password": "secret"},
    )
    assert response_email.status_code == 400
    assert response_email.json()["detail"] == "Email already registered"


def test_login_success_and_token_validation(client):
    client.post(
        "/auth/register",
        json={"username": "carol", "email": "carol@example.com", "password": "secret"},
    )

    response = client.post(
        "/auth/login", data={"username": "carol", "password": "secret"}
    )
    assert response.status_code == 200
    token = response.json()["access_token"]

    me_resp = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "carol"


def test_login_fail_wrong_credentials_or_inactive(client):
    client.post(
        "/auth/register",
        json={"username": "dave", "email": "dave@example.com", "password": "secret"},
    )

    bad_resp = client.post(
        "/auth/login", data={"username": "dave", "password": "wrong"}
    )
    assert bad_resp.status_code == 401
    assert bad_resp.json()["detail"] == "Incorrect username or password"

    with Session(engine) as session:
        user = User(
            username="erin",
            email="erin@example.com",
            password_hash=get_password_hash("secret"),
            active=False,
        )
        session.add(user)
        session.commit()

    inactive_resp = client.post(
        "/auth/login", data={"username": "erin", "password": "secret"}
    )
    assert inactive_resp.status_code == 403
    assert inactive_resp.json()["detail"] == "User inactive"
