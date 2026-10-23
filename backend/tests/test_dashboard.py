"""The Dashboard, Activity (the bell) and /api/config."""
from backend.app.cli import seed_reference_experiment
from backend.app.extensions import db
from backend.app.models import ActivityEvent, Experiment

from .conftest import csrf, signup


def add_events(user_id, n):
    for i in range(n):
        db.session.add(ActivityEvent(user_id=user_id, type="experiment.completed", message=f"run {i} finished."))
    db.session.commit()


def test_dashboard_for_a_new_user_shows_the_reference_run(client):
    seed_reference_experiment()
    db.session.commit()
    signup(client)
    data = client.get("/api/dashboard").get_json()["data"]
    assert data["kpis"]["experiments"] == 0 and data["kpis"]["chats"] == 0
    assert data["kpis"]["best_heldout"] == 1.0                  # the published run: 60/60 held-out
    assert data["latest"]["experiment"]["name"] == "Published reference run"
    assert data["latest"]["metrics"][0]["val_loss"] is not None
    assert data["active_experiment"] is None and data["activity"] == [] and data["unread"] == 0


def test_dashboard_counts_your_things(client):
    me = signup(client)
    client.post("/api/chat", headers=csrf(client), json={"message": "Where does Leela live?"})
    db.session.add(Experiment(owner_id=me["id"], name="mine", pretrain_steps=150, finetune_steps=60, status="running"))
    db.session.commit()
    add_events(me["id"], 7)
    data = client.get("/api/dashboard").get_json()["data"]
    assert data["kpis"] == {"experiments": 1, "completed": 0, "active": 1, "chats": 1, "questions": 1,
                                  "best_heldout": None}
    assert data["active_experiment"]["name"] == "mine" and len(data["activity"]) == 5 and data["unread"] == 7


def test_activity_paging_and_mark_read(app):
    me, other = app.test_client(), app.test_client()
    mine = signup(me)
    theirs = signup(other, email="o@example.com")
    add_events(mine["id"], 25)
    add_events(theirs["id"], 1)
    r = me.get("/api/activity?per_page=10").get_json()
    assert r["meta"]["total"] == 25 and r["meta"]["unread"] == 25 and r["data"][0]["message"] == "run 24 finished."

    first_two = [e["id"] for e in r["data"][:2]]
    other_id = db.session.query(ActivityEvent).filter_by(user_id=theirs["id"]).one().id
    r = me.post("/api/activity/read", headers=csrf(me), json={"ids": first_two + [other_id]})
    assert r.get_json()["data"] == {"marked": 2, "unread": 23}           # someone else's event is untouched
    assert me.get("/api/activity?unread=true").get_json()["meta"]["total"] == 23

    assert me.post("/api/activity/read", headers=csrf(me), json={}).get_json()["data"]["unread"] == 0
    assert other.get("/api/activity").get_json()["meta"]["unread"] == 1
    assert me.post("/api/activity/read", json={}).status_code == 401      # CSRF header required


def test_config_is_public(client):
    data = client.get("/api/config").get_json()["data"]
    assert [p["name"] for p in data["presets"]] == ["quick", "short", "full"]
    assert data["presets"][0] == {"name": "quick", "pretrain_steps": 150, "finetune_steps": 60, "minutes": "4-7"}
    assert data["limits"]["lora_rank"] == {"min": 1, "max": 32}
    assert [m["id"] for m in data["models"]] == ["base", "full", "lora"]
    assert data["training_enabled"] is True


def test_health_reports_models(client):
    assert client.get("/api/health").get_json()["data"]["models"] in ("available", "loaded")
