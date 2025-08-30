import sys
import os
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

os.environ.setdefault("database_url", "sqlite:///:memory:")
os.environ.setdefault("secret_key", "testsecret")

from fastapi.testclient import TestClient
from app.main import app
from app.models.user import User
from app.api.endpoints.auth import get_current_user


def test_me_accepts_json_string_preferences():
    client = TestClient(app)

    user = User(
        id=1,
        username="alice",
        email="alice@example.com",
        password_hash="hashed",
        preferences='{"theme": "dark"}',
    )

    app.dependency_overrides[get_current_user] = lambda: user

    response = client.get("/auth/me")

    assert response.status_code == 200
    assert response.json()["preferences"]["theme"] == "dark"

    app.dependency_overrides.clear()
