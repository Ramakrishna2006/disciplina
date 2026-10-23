"""The health endpoint, the JSON error format and the security headers."""
from backend.app import create_app
from backend.app.extensions import db


def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.get_json()["data"]
    assert data["status"] == "ok" and data["database"] == "ok"
    assert data["environment"] == "testing" and data["app"] == "Disciplina Studio"


def test_health_reports_database_down(client, monkeypatch):
    def broken(*_args, **_kwargs):
        raise RuntimeError("database is down")
    monkeypatch.setattr(db.session, "execute", broken)
    r = client.get("/api/health")
    assert r.status_code == 503
    data = r.get_json()["data"]
    assert data["status"] == "degraded" and data["database"] == "unreachable"


def test_unknown_api_route_is_json_404(client):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404
    err = r.get_json()["error"]
    assert err["code"] == "not_found" and err["message"] and err["fields"] == {}


def test_wrong_method_is_json_405(client):
    r = client.post("/api/health")
    assert r.status_code == 405 and r.get_json()["error"]["code"] == "method_not_allowed"


def test_every_response_has_a_request_id(client):
    r = client.get("/api/health")
    assert len(r.headers["X-Request-ID"]) == 12
    assert client.get("/api/health", headers={"X-Request-ID": "render-abc-12345"}).headers["X-Request-ID"] == "render-abc-12345"
    assert client.get("/api/health", headers={"X-Request-ID": "<script>"}).headers["X-Request-ID"] != "<script>"


def test_unexpected_error_hides_details(tmp_path):
    app = create_app("testing", SQLALCHEMY_DATABASE_URI=f"sqlite:///{(tmp_path / 'x.db').as_posix()}")

    @app.get("/api/boom")
    def boom():
        raise ValueError("secret internal detail")

    r = app.test_client().get("/api/boom")
    assert r.status_code == 500
    body = r.get_data(as_text=True)
    assert "secret internal detail" not in body and "Traceback" not in body
    err = r.get_json()["error"]
    assert err["code"] == "server_error" and err["request_id"] == r.headers["X-Request-ID"]
    assert err["request_id"] in err["message"]


def test_security_headers(client):
    h = client.get("/api/health").headers
    assert h["X-Content-Type-Options"] == "nosniff"
    assert h["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in h["Content-Security-Policy"]
    assert h["Cache-Control"] == "no-store"
    assert "Strict-Transport-Security" not in h        # HTTPS-only header is for production


def test_large_body_rejected(app):
    @app.post("/api/echo-size")
    def echo_size():
        from flask import request
        return {"size": len(request.get_data())}

    r = app.test_client().post("/api/echo-size", data=b"x" * (64 * 1024 + 1))
    assert r.status_code == 413 and r.get_json()["error"]["code"] == "payload_too_large"
