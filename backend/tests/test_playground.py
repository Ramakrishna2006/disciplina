"""Chat, saved conversations, the tokenizer and the embedding map, with the real published models."""
import pytest

from backend.app.extensions import db
from backend.app.models import ChatMessage, ChatSession

from .conftest import build_app, csrf, signup


def ask(client, message="Where does Leela live?", **body):
    return client.post("/api/chat", headers=csrf(client), json={"message": message, **body})


def test_chat_answers_a_held_out_question_and_saves_it(client):
    signup(client)
    r = ask(client)                                    # Leela is held out: never seen as Q&A
    assert r.status_code == 200, r.get_json()
    data = r.get_json()["data"]
    assert data["reply"] == "Surat" and data["tokens"] >= 1 and data["latency_ms"] >= 0
    assert [m["role"] for m in data["messages"]] == ["user", "assistant"]
    s = db.session.get(ChatSession, data["session_id"])
    assert s.title == "Where does Leela live?" and s.model == "lora" and len(s.messages) == 2


def test_chat_continues_a_session(client):
    signup(client)
    sid = ask(client).get_json()["data"]["session_id"]
    r = ask(client, "What is the job of Leela?", session_id=sid, model="full")
    assert r.get_json()["data"]["session_id"] == sid
    assert db.session.query(ChatMessage).count() == 4
    assert db.session.get(ChatSession, sid).model == "full"


def test_base_model_continues_text(client):
    signup(client)
    r = ask(client, "Meera", model="base", temperature=0.8, top_k=10)
    assert r.status_code == 200 and r.get_json()["data"]["reply"]


@pytest.mark.parametrize("body, field", [
    ({"message": ""}, "message"), ({"message": "   "}, "message"), ({"message": "x" * 501}, "message"),
    ({"message": "hi", "model": "gpt"}, "model"), ({"message": "hi", "temperature": 2.1}, "temperature"),
    ({"message": "hi", "top_k": 0}, "top_k"), ({"message": "hi", "top_k": 101}, "top_k"),
    ({"message": "hi", "extra": 1}, "extra"),
])
def test_chat_validation(client, body, field):
    signup(client)
    r = client.post("/api/chat", headers=csrf(client), json=body)
    assert r.status_code == 400 and field in r.get_json()["error"]["fields"]


def test_chat_needs_login_and_csrf(client):
    assert ask(client).status_code == 401
    signup(client)
    assert client.post("/api/chat", json={"message": "hi"}).status_code == 401   # no CSRF header


def test_someone_elses_session_is_not_found(app):
    asha, ravi = app.test_client(), app.test_client()
    signup(asha)
    signup(ravi, email="ravi@example.com", name="Ravi")
    sid = ask(asha).get_json()["data"]["session_id"]
    assert ask(ravi, session_id=sid).status_code == 404
    assert ravi.get(f"/api/chat/sessions/{sid}").status_code == 404
    assert ravi.patch(f"/api/chat/sessions/{sid}", headers=csrf(ravi), json={"title": "mine"}).status_code == 404
    assert ravi.delete(f"/api/chat/sessions/{sid}", headers=csrf(ravi)).status_code == 404
    assert ravi.get("/api/chat/sessions").get_json()["meta"]["total"] == 0


def test_session_list_rename_delete(client):
    signup(client)
    first = ask(client, "Where does Asha live?").get_json()["data"]["session_id"]
    second = ask(client).get_json()["data"]["session_id"]
    ask(client, "What does Leela love?", session_id=first)       # first is now the newest
    r = client.get("/api/chat/sessions").get_json()
    assert [s["id"] for s in r["data"]] == [first, second] and r["meta"]["total"] == 2
    assert r["data"][0]["message_count"] == 4 and r["data"][0]["last_message"]

    r = client.patch(f"/api/chat/sessions/{first}", headers=csrf(client), json={"title": "  Leela  facts "})
    assert r.get_json()["data"]["session"]["title"] == "Leela facts"
    assert client.patch(f"/api/chat/sessions/{first}", headers=csrf(client), json={"title": ""}).status_code == 400

    detail = client.get(f"/api/chat/sessions/{first}").get_json()["data"]
    assert len(detail["messages"]) == 4 and detail["messages"][0]["role"] == "user"
    assert client.delete(f"/api/chat/sessions/{first}", headers=csrf(client)).status_code == 204
    assert db.session.query(ChatMessage).count() == 2            # its messages went with it


def test_chat_rate_limit_is_per_user(tmp_path):
    from flask_migrate import upgrade
    app = build_app(tmp_path, RATELIMIT_CHAT="2 per minute")
    with app.app_context():
        upgrade()
        a, b = app.test_client(), app.test_client()
        signup(a)
        signup(b, email="b@example.com")
        assert [ask(a).status_code for _ in range(3)] == [200, 200, 429]
        assert ask(b).status_code == 200                         # another user is not affected
        db.session.remove()
        db.engine.dispose()


def test_tokenize(client):
    signup(client)
    r = client.post("/api/tokenize", headers=csrf(client), json={"text": "Asha lives in Pune."})
    data = r.get_json()["data"]
    assert "".join(t["text"] for t in data["tokens"]) == "Asha lives in Pune."
    assert data["count"] == len(data["tokens"]) < data["characters"] and data["chars_per_token"] > 1
    assert client.post("/api/tokenize", headers=csrf(client), json={"text": ""}).get_json()["data"]["count"] == 0
    assert client.post("/api/tokenize", headers=csrf(client), json={"text": "x" * 1001}).status_code == 400


def test_embeddings_map_and_neighbors(client):
    signup(client)
    points = client.get("/api/embeddings").get_json()["data"]["points"]
    assert {p["category"] for p in points} == {"city", "job", "food"} and len(points) >= 25
    assert all(0 <= p["x"] <= 1 and 0 <= p["y"] <= 1 for p in points)

    r = client.get("/api/embeddings/neighbors?word=Pune&k=3").get_json()["data"]
    assert len(r["neighbors"]) == 3 and r["neighbors"][0]["similarity"] >= r["neighbors"][-1]["similarity"]
    assert client.get("/api/embeddings/neighbors?word=Bengaluru").status_code == 404
    assert client.get("/api/embeddings/neighbors?word=Pune&k=11").status_code == 400
    assert client.get("/api/embeddings/neighbors").status_code == 400


def test_missing_models_answer_503(tmp_path):
    from flask_migrate import upgrade
    app = build_app(tmp_path, ARTIFACTS_DIR=tmp_path / "nothing-here")
    with app.app_context():
        upgrade()
        c = app.test_client()
        signup(c)
        r = ask(c)
        assert r.status_code == 503 and r.get_json()["error"]["code"] == "models_unavailable"
        assert c.get("/api/health").get_json()["data"]["models"] == "missing"
        db.session.remove()
        db.engine.dispose()
