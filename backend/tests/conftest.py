"""
Shared test setup. Every test gets a brand-new app with its own temporary SQLite file, built by
running the real migrations (not create_all), so the tests check the schema you will deploy.
Nothing is written to backend/instance, and your development database is never touched.
"""
import pytest
from flask_migrate import upgrade

from backend.app import create_app
from backend.app.extensions import db


@pytest.fixture
def app(tmp_path):
    app = create_app("testing", SQLALCHEMY_DATABASE_URI=f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
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

    def _make(email="asha@example.com", name="Asha", password="correct horse battery"):
        user = User(email=email, name=name)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user
    return _make
