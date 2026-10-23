"""The Dataset page: the 40 seeded people, searched, filtered, sorted and paged."""
import pytest

from backend.app.cli import seed_people
from backend.app.extensions import db

from .conftest import signup


@pytest.fixture
def seeded(client):
    seed_people()
    db.session.commit()
    signup(client)
    return client


def test_all_people_with_paging(seeded):
    r = seeded.get("/api/people?per_page=15&page=3").get_json()
    assert r["meta"] == {"page": 3, "per_page": 15, "total": 40, "pages": 3}
    assert len(r["data"]) == 10
    names = [p["name"] for p in seeded.get("/api/people?per_page=100").get_json()["data"]]
    assert names == sorted(names) and len(names) == 40


def test_filters_and_search(seeded):
    held = seeded.get("/api/people?split=held-out&per_page=100").get_json()
    assert held["meta"]["total"] > 0 and all(p["split"] == "held-out" for p in held["data"])
    leela = seeded.get("/api/people?search=leel").get_json()["data"]
    assert [p["name"] for p in leela] == ["Leela"] and leela[0]["city"] == "Surat"
    surat = seeded.get("/api/people?city=Surat&per_page=100").get_json()["data"]
    assert surat and all(p["city"] == "Surat" for p in surat)
    assert seeded.get("/api/people?search=%25").get_json()["meta"]["total"] == 0   # % is a letter, not a wildcard


def test_sorting(seeded):
    rows = seeded.get("/api/people?sort=city&order=desc&per_page=100").get_json()["data"]
    assert [p["city"] for p in rows] == sorted((p["city"] for p in rows), reverse=True)


@pytest.mark.parametrize("query", ["sort=password", "order=up", "per_page=101", "page=0", "split=all", "x=1"])
def test_bad_queries(seeded, query):
    assert seeded.get(f"/api/people?{query}").status_code == 400


def test_facets(seeded):
    f = seeded.get("/api/people/facets").get_json()["data"]
    assert f["total"] == 40
    for column in ("city", "job", "food", "split"):
        assert sum(x["count"] for x in f[column]) == 40
    assert {x["value"] for x in f["split"]} == {"fine-tuning", "held-out"}


def test_people_need_login(client):
    assert client.get("/api/people").status_code == 401
