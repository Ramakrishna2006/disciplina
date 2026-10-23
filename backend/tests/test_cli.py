"""flask create-admin: the password is typed in, checked with the same rules as the website."""
from backend.app.extensions import db
from backend.app.models import User

from .conftest import PASSWORD


def invoke(app, *args, input=None):
    return app.test_cli_runner().invoke(args=["create-admin", *args], input=input)


def test_create_admin(app):
    r = invoke(app, "--email", "Admin@Example.com", "--name", "Rama", input=f"{PASSWORD}\n{PASSWORD}\n")
    assert r.exit_code == 0, r.output
    admin = db.session.query(User).one()
    assert (admin.email, admin.name, admin.role) == ("admin@example.com", "Rama", "admin")
    assert admin.check_password(PASSWORD) and PASSWORD not in r.output   # hidden input, never echoed


def test_create_admin_rejects_weak_password(app):
    r = invoke(app, "--email", "admin@example.com", "--name", "Rama", input="short\nshort\n")
    assert r.exit_code != 0 and "password" in r.output
    assert db.session.query(User).count() == 0


def test_create_admin_promotes_existing_account(app, make_user):
    make_user(email="asha@example.com")
    r = invoke(app, "--email", "asha@example.com", "--name", "ignored")
    assert r.exit_code == 0 and "now an admin" in r.output
    user = db.session.query(User).one()
    assert user.role == "admin" and user.check_password(PASSWORD)          # password unchanged
