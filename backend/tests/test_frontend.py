"""Flask serves the built React app: real files, index.html for app pages, JSON for /api."""
import pytest
from flask_migrate import upgrade

from backend.app.extensions import db

from .conftest import build_app


@pytest.fixture
def site(tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><div id=root></div>", encoding="utf-8")
    (dist / "assets" / "index-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (dist / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("outside dist", encoding="utf-8")
    app = build_app(tmp_path, FRONTEND_DIST=dist)
    with app.app_context():
        upgrade()
        yield app.test_client()
        db.session.remove()
        db.engine.dispose()


def test_app_pages_get_index_html(site):
    for path in ("/", "/login", "/app", "/app/experiments/7"):
        r = site.get(path)
        assert r.status_code == 200 and b'id=root' in r.data, path
        assert r.headers["Cache-Control"] == "no-cache"
        assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]


def test_built_files_are_served_and_cached(site):
    r = site.get("/assets/index-abc123.js")
    assert r.status_code == 200 and r.data == b"console.log(1)"
    assert "immutable" in r.headers["Cache-Control"]
    assert site.get("/favicon.svg").status_code == 200


def test_api_addresses_stay_json(site):
    r = site.get("/api/not-a-real-endpoint")
    assert r.status_code == 404 and r.get_json()["error"]["code"] == "not_found"
    assert site.get("/api").status_code == 404
    assert site.get("/api/health").get_json()["data"]["status"] == "ok"


def test_files_outside_dist_are_never_served(site):
    for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/assets/../../secret.txt"):
        r = site.get(path)
        assert b"outside dist" not in r.data, path


def test_clear_message_when_frontend_not_built(tmp_path):
    app = build_app(tmp_path, FRONTEND_DIST=tmp_path / "missing")
    r = app.test_client().get("/")
    assert r.status_code == 404 and b"npm run build" in r.data
