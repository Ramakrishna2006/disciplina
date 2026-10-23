"""Register, login, refresh, logout, me: the happy paths, the errors, and the security rules."""
import time
from datetime import timedelta

import pytest
from flask_migrate import upgrade

from backend.app.extensions import db
from backend.app.models import TokenBlocklist, User

from .conftest import PASSWORD, build_app, csrf, signup

ACCESS, REFRESH = "access_token_cookie", "refresh_token_cookie"


# ----------------------------------------------------------------------------- register
def test_register_signs_you_in(client):
    r = client.post("/api/auth/register", json={"name": "  Asha  Rao ", "email": "Asha@Example.com",
                                                "password": PASSWORD})
    assert r.status_code == 201
    user = r.get_json()["data"]["user"]
    assert user["email"] == "asha@example.com" and user["name"] == "Asha Rao" and user["role"] == "member"
    assert "password" not in str(user) and "password_hash" not in user
    cookies = r.headers.getlist("Set-Cookie")
    access = next(c for c in cookies if c.startswith(ACCESS))
    assert "HttpOnly" in access and "SameSite=Lax" in access and "Path=/api/" in access
    assert "Secure" not in access                       # plain http://localhost works in development
    csrf_cookie = next(c for c in cookies if c.startswith("csrf_access_token"))
    assert "HttpOnly" not in csrf_cookie                # the frontend must be able to read this one
    assert client.get("/api/auth/me").get_json()["data"]["user"]["email"] == "asha@example.com"


@pytest.mark.parametrize("body, field", [
    ({"name": "Asha", "email": "not-an-email", "password": PASSWORD}, "email"),
    ({"name": "Asha", "email": "a@b.co", "password": "short"}, "password"),
    ({"name": "Asha", "email": "a@b.co", "password": "x" * 129}, "password"),
    ({"name": "   ", "email": "a@b.co", "password": PASSWORD}, "name"),
    ({"name": "A" * 81, "email": "a@b.co", "password": PASSWORD}, "name"),
    ({"email": "a@b.co", "password": PASSWORD}, "name"),
    ({"name": "Asha", "email": "a@b.co", "password": PASSWORD, "role": "admin"}, "role"),
    ({"name": 42, "email": "a@b.co", "password": PASSWORD}, "name"),
])
def test_register_validation(client, body, field):
    r = client.post("/api/auth/register", json=body)
    assert r.status_code == 400
    err = r.get_json()["error"]
    assert err["code"] == "validation_error" and field in err["fields"], err
    assert db.session.query(User).count() == 0


def test_register_needs_a_json_object(client):
    for data in ("not json", "[1, 2]"):
        r = client.post("/api/auth/register", data=data, content_type="application/json")
        assert r.status_code == 400 and r.get_json()["error"]["code"] == "bad_request"


def test_register_duplicate_email_any_case(client):
    signup(client)
    r = client.post("/api/auth/register", json={"name": "B", "email": "ASHA@example.com", "password": PASSWORD})
    assert r.status_code == 409 and r.get_json()["error"]["code"] == "email_taken"


def test_password_spaces_are_kept(client, app):
    signup(client, password="  spaced out pass  ")
    client.post("/api/auth/logout", headers=csrf(client))
    assert client.post("/api/auth/login", json={"email": "asha@example.com",
                                                "password": "spaced out pass"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "asha@example.com",
                                                "password": "  spaced out pass  "}).status_code == 200


# ----------------------------------------------------------------------------- login
def test_login_and_me(client, make_user):
    make_user()
    r = client.post("/api/auth/login", json={"email": " ASHA@example.com ", "password": PASSWORD})
    assert r.status_code == 200
    me = client.get("/api/auth/me").get_json()["data"]["user"]
    assert me["name"] == "Asha" and me["last_login_at"] is not None


def test_login_errors_do_not_reveal_accounts(client, make_user):
    make_user()
    wrong_password = client.post("/api/auth/login", json={"email": "asha@example.com", "password": "nope-nope-nope"})
    unknown_email = client.post("/api/auth/login", json={"email": "who@example.com", "password": "nope-nope-nope"})
    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.get_json() == unknown_email.get_json()
    assert not wrong_password.headers.getlist("Set-Cookie")


def test_disabled_account(client, make_user):
    make_user(is_active=False)
    r = client.post("/api/auth/login", json={"email": "asha@example.com", "password": "wrong-password"})
    assert r.status_code == 401                             # wrong password: no hint the account exists
    r = client.post("/api/auth/login", json={"email": "asha@example.com", "password": PASSWORD})
    assert r.status_code == 403 and r.get_json()["error"]["code"] == "account_disabled"


def test_disabling_an_account_ends_its_sessions(client):
    signup(client)
    user = db.session.query(User).one()
    user.is_active = False
    db.session.commit()
    r = client.get("/api/auth/me")
    assert r.status_code == 401 and r.get_json()["error"]["code"] == "account_unavailable"


# ----------------------------------------------------------------------------- me, CSRF
def test_me_requires_login(client):
    r = client.get("/api/auth/me")
    assert r.status_code == 401 and r.get_json()["error"]["code"] == "not_signed_in"


def test_forged_token_is_rejected(client):
    client.set_cookie(ACCESS, "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.forged", path="/api/")
    r = client.get("/api/auth/me")
    assert r.status_code == 401 and r.get_json()["error"]["code"] == "invalid_token"


def test_change_requests_need_the_csrf_header(client):
    signup(client)
    r = client.patch("/api/users/me", json={"theme": "dark"})                        # no header
    assert r.status_code == 401 and r.get_json()["error"]["code"] == "csrf_failed"
    r = client.patch("/api/users/me", json={"theme": "dark"}, headers={"X-CSRF-TOKEN": "guess"})
    assert r.status_code == 401 and r.get_json()["error"]["code"] == "csrf_failed"
    r = client.patch("/api/users/me", json={"theme": "dark"}, headers=csrf(client))
    assert r.status_code == 200
    assert client.get("/api/auth/me").status_code == 200                             # GET needs no header


# ----------------------------------------------------------------------------- refresh
def test_expired_access_token_and_refresh(tmp_path):
    app = build_app(tmp_path, JWT_ACCESS_TOKEN_EXPIRES=timedelta(seconds=1))    # access tokens last 1 second
    with app.app_context():
        upgrade()
        client = app.test_client()
        signup(client)
        time.sleep(2)
        r = client.get("/api/auth/me")
        assert r.status_code == 401 and r.get_json()["error"]["code"] == "token_expired"
        assert client.post("/api/auth/refresh").status_code == 401                 # CSRF header required
        r = client.post("/api/auth/refresh", headers=csrf(client, "refresh"))
        assert r.status_code == 200 and r.get_json()["data"]["user"]["email"] == "asha@example.com"
        db.session.remove()
        db.engine.dispose()


def test_refresh_needs_the_refresh_token(client):
    signup(client)
    client.delete_cookie(REFRESH, path="/api/auth/")
    assert client.post("/api/auth/refresh", headers=csrf(client, "refresh")).status_code == 401


def test_access_token_cannot_be_used_as_refresh_token(client):
    signup(client)
    access = client.get_cookie(ACCESS, path="/api/").value
    client.set_cookie(REFRESH, access, path="/api/auth/")
    assert client.post("/api/auth/refresh", headers=csrf(client, "refresh")).status_code == 401


# ----------------------------------------------------------------------------- logout
def test_logout_revokes_copied_tokens(client):
    signup(client)
    stolen = client.get_cookie(ACCESS, path="/api/").value
    r = client.post("/api/auth/logout", headers=csrf(client))
    assert r.status_code == 200 and r.get_json()["data"] == {"signed_out": True}
    assert db.session.query(TokenBlocklist).count() == 2                          # access + refresh
    assert client.get("/api/auth/me").status_code == 401                          # cookies cleared
    client.set_cookie(ACCESS, stolen, path="/api/")                               # replay the copy
    r = client.get("/api/auth/me")
    assert r.status_code == 401 and r.get_json()["error"]["code"] == "token_revoked"


def test_logout_needs_csrf_when_signed_in(client):
    signup(client)
    r = client.post("/api/auth/logout")
    assert r.status_code == 401 and r.get_json()["error"]["code"] == "csrf_failed"
    assert client.get("/api/auth/me").status_code == 200                          # still signed in


def test_logout_when_not_signed_in_is_harmless(client):
    assert client.post("/api/auth/logout").status_code == 200
    client.set_cookie(ACCESS, "garbage", path="/api/")                            # unreadable cookie
    assert client.post("/api/auth/logout").status_code == 200


def test_logout_with_expired_token(tmp_path):
    app = build_app(tmp_path, JWT_ACCESS_TOKEN_EXPIRES=timedelta(seconds=1))
    with app.app_context():
        upgrade()
        client = app.test_client()
        signup(client)
        time.sleep(2)
        assert client.get("/api/auth/me").get_json()["error"]["code"] == "token_expired"
        assert client.post("/api/auth/logout", headers=csrf(client)).status_code == 200
        assert db.session.query(TokenBlocklist).count() == 2
        db.session.remove()
        db.engine.dispose()
