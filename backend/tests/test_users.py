"""Profile, password change and account deletion: only ever your own account."""
import time

import pytest

from backend.app.extensions import db
from backend.app.models import ChatSession, Experiment, Metric, User

from .conftest import PASSWORD, csrf, signup

NEW_PASSWORD = "an even better passphrase"


def test_update_profile(client):
    signup(client)
    r = client.patch("/api/users/me", headers=csrf(client),
                     json={"name": "Asha R", "theme": "dark", "default_model": "full", "default_temperature": 0.7})
    assert r.status_code == 200
    user = r.get_json()["data"]["user"]
    assert (user["name"], user["theme"], user["default_model"], user["default_temperature"]) == \
        ("Asha R", "dark", "full", 0.7)


@pytest.mark.parametrize("body, field", [
    ({"theme": "pink"}, "theme"), ({"default_model": "gpt"}, "default_model"),
    ({"default_temperature": 2.5}, "default_temperature"), ({"default_temperature": -1}, "default_temperature"),
    ({"name": ""}, "name"), ({"role": "admin"}, "role"), ({"email": "x@y.z"}, "email"),
    ({}, "body"), ({"theme": None}, "body"),
])
def test_update_profile_validation(client, body, field):
    signup(client)
    r = client.patch("/api/users/me", headers=csrf(client), json=body)
    assert r.status_code == 400 and field in r.get_json()["error"]["fields"], r.get_json()
    assert db.session.query(User).one().role == "member"        # nobody can make themselves admin


def test_change_password(client):
    signup(client)
    r = client.post("/api/users/me/password", headers=csrf(client),
                    json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})
    assert r.status_code == 200
    assert client.get("/api/auth/me").status_code == 200         # this browser stays signed in
    client.post("/api/auth/logout", headers=csrf(client))
    login = lambda pw: client.post("/api/auth/login", json={"email": "asha@example.com", "password": pw})  # noqa: E731
    assert login(PASSWORD).status_code == 401 and login(NEW_PASSWORD).status_code == 200


def test_change_password_signs_out_other_devices(app):
    laptop, phone = app.test_client(), app.test_client()
    signup(laptop)
    phone.post("/api/auth/login", json={"email": "asha@example.com", "password": PASSWORD})
    assert phone.get("/api/auth/me").status_code == 200
    time.sleep(1.1)       # tokens carry whole seconds; the phone's token must be from an earlier second
    laptop.post("/api/users/me/password", headers=csrf(laptop),
                json={"current_password": PASSWORD, "new_password": NEW_PASSWORD})
    r = phone.get("/api/auth/me")
    assert r.status_code == 401 and r.get_json()["error"]["code"] == "token_revoked"
    assert laptop.get("/api/auth/me").status_code == 200


@pytest.mark.parametrize("body, field", [
    ({"current_password": "wrong password!", "new_password": NEW_PASSWORD}, "current_password"),
    ({"current_password": PASSWORD, "new_password": "short"}, "new_password"),
    ({"current_password": PASSWORD, "new_password": PASSWORD}, "new_password"),
])
def test_change_password_errors(client, body, field):
    signup(client)
    r = client.post("/api/users/me/password", headers=csrf(client), json=body)
    assert r.status_code == 400 and field in r.get_json()["error"]["fields"]


def test_delete_account_deletes_all_your_data(client, make_user):
    other = make_user(email="other@example.com")
    signup(client)
    me = db.session.query(User).filter_by(email="asha@example.com").one()
    for owner in (me, other):
        exp = Experiment(owner_id=owner.id, name="run", pretrain_steps=150, finetune_steps=60)
        exp.metrics.append(Metric(phase="pretrain", step=0, train_loss=6.4))
        db.session.add_all([exp, ChatSession(user_id=owner.id, title="chat")])
    db.session.commit()

    assert client.delete("/api/users/me", headers=csrf(client), json={"password": "wrong password!"}).status_code == 400
    r = client.delete("/api/users/me", headers=csrf(client), json={"password": PASSWORD})
    assert r.status_code == 204 and r.get_data() == b""
    db.session.expire_all()
    assert [u.email for u in db.session.query(User)] == ["other@example.com"]     # only yours is gone
    assert db.session.query(Experiment).count() == db.session.query(ChatSession).count() == 1
    assert db.session.query(Metric).count() == 1
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/login", json={"email": "asha@example.com", "password": PASSWORD}).status_code == 401


def test_users_endpoints_require_login(client):
    assert client.patch("/api/users/me", json={"theme": "dark"}).status_code == 401
    assert client.post("/api/users/me/password", json={}).status_code == 401
    assert client.delete("/api/users/me", json={"password": PASSWORD}).status_code == 401
