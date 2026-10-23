"""
Shared test setup. Every test gets a brand-new app with its own temporary SQLite file, built by
running the real migrations (not create_all), so the tests check the schema you will deploy.
Nothing is written to backend/instance, and your development database is never touched.
"""
import pytest
from flask_migrate import upgrade

from backend.app import create_app
from backend.app.extensions import db

PASSWORD = "correct horse battery"


def build_app(tmp_path, **overrides):
    app = create_app("testing", SQLALCHEMY_DATABASE_URI=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
                     **overrides)
    return app


@pytest.fixture
def app(tmp_path):
    # Generous limits here; test_rate_limits.py checks the real ones with its own app.
    app = build_app(tmp_path, RATELIMIT_LOGIN="1000 per minute", RATELIMIT_REGISTER="1000 per hour")
    with app.app_context():
        upgrade()
        yield app
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def make_user(app):
    from backend.app.models import User

    def _make(email="asha@example.com", name="Asha", password=PASSWORD, **fields):
        user = User(email=email, name=name, **fields)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user
    return _make


def csrf(client, kind="access"):
    """The X-CSRF-TOKEN header a real frontend would send (copied from the readable CSRF cookie)."""
    cookie = client.get_cookie(f"csrf_{kind}_token")
    return {"X-CSRF-TOKEN": cookie.value} if cookie else {}


def signup(client, email="asha@example.com", name="Asha", password=PASSWORD):
    r = client.post("/api/auth/register", json={"name": name, "email": email, "password": password})
    assert r.status_code == 201, r.get_json()
    return r.get_json()["data"]["user"]
