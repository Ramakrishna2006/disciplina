"""The real rate limits: login 5 per minute, register 3 per hour (per IP address)."""
import pytest
from flask_migrate import upgrade

from backend.app.extensions import db

from .conftest import PASSWORD, build_app


@pytest.fixture
def strict_client(tmp_path):
    app = build_app(tmp_path)                    # default limits from config.py
    with app.app_context():
        upgrade()
        yield app.test_client()
        db.session.remove()
        db.engine.dispose()


def test_login_is_limited(strict_client):
    body = {"email": "nobody@example.com", "password": "wrong password!"}
    codes = [strict_client.post("/api/auth/login", json=body).status_code for _ in range(6)]
    assert codes == [401] * 5 + [429]
    r = strict_client.post("/api/auth/login", json=body)
    assert r.status_code == 429 and r.get_json()["error"]["code"] == "rate_limited"
    assert "Retry-After" in r.headers


def test_register_is_limited(strict_client):
    codes = [strict_client.post("/api/auth/register", json={"name": "U", "email": f"u{i}@example.com",
                                                           "password": PASSWORD}).status_code for i in range(4)]
    assert codes == [201, 201, 201, 429]


def test_limits_are_per_ip_address(strict_client):
    body = {"email": "nobody@example.com", "password": "wrong password!"}
    for _ in range(5):
        strict_client.post("/api/auth/login", json=body)
    other = strict_client.post("/api/auth/login", json=body, environ_base={"REMOTE_ADDR": "10.0.0.2"})
    assert other.status_code == 401              # a different visitor is not blocked
