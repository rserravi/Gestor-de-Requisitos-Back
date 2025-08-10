import sys
import os
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("database_url", "sqlite:///:memory:")

from fastapi.testclient import TestClient
from app.main import app
from app.models.user import User
from app.api.endpoints.auth import get_current_user, get_session


class DummySession:
    def add(self, obj):
        pass

    def commit(self):
        pass

    def refresh(self, obj):
        pass


def override_get_session():
    yield DummySession()


def test_update_user_data():
    client = TestClient(app)

    user = User(
        id=1,
        username="alice",
        email="alice@example.com",
        password_hash="hashed",
        avatar="old.png",
        preferences={},
    )

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = override_get_session

    payload = {"username": "alice2", "email": "alice2@example.com", "avatar": "new.png"}
    response = client.put("/auth/me", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["username"] == "alice2"
    assert data["email"] == "alice2@example.com"
    assert data["avatar"] == "new.png"

    app.dependency_overrides.clear()


def test_update_preferences():
    client = TestClient(app)

    user = User(
        id=1,
        username="alice",
        email="alice@example.com",
        password_hash="hashed",
        preferences={},
    )

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_session] = override_get_session

    prefs = {"theme": "dark", "notifications": False, "language": "es", "timezone": "Europe/Madrid"}
    response = client.put("/auth/preferences", json=prefs)

    assert response.status_code == 200
    assert response.json() == prefs

    app.dependency_overrides.clear()

