"""
The Dataset page: the 40 people the models learned about.

    GET /api/people           search, filter, sort and page through them
    GET /api/people/facets    how many people have each city, job, food and split (for the filters)
"""
from flask import Blueprint
from flask_jwt_extended import jwt_required
from sqlalchemy import func, or_, select

from ..extensions import db
from ..models import Person
from ..schemas import parse_query
from ..schemas.studio import PeopleQuery
from ..utils.pagination import paginate
from ..utils.responses import ok

bp = Blueprint("people", __name__, url_prefix="/api/people")
FACETS = ("city", "job", "food", "split")


@bp.get("")
@jwt_required()
def list_people():
    q = parse_query(PeopleQuery)
    stmt = select(Person)
    if q.search:
        # The search text is a bound parameter, never pasted into the SQL (no SQL injection);
        # \ % _ are escaped so they match literally.
        like = "%" + q.search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        stmt = stmt.where(or_(*(getattr(Person, c).ilike(like, escape="\\") for c in ("name", *FACETS))))
    for column in FACETS:
        value = getattr(q, column)
        if value:
            stmt = stmt.where(getattr(Person, column) == value)
    col = getattr(Person, q.sort)
    stmt = stmt.order_by(col.desc() if q.order == "desc" else col.asc(), Person.name.asc())
    people, meta = paginate(stmt, q.page, q.per_page)
    return ok([p.to_dict() for p in people], meta=meta)


@bp.get("/facets")
@jwt_required()
def facets():
    data = {}
    for column in FACETS:
        col = getattr(Person, column)
        rows = db.session.execute(select(col, func.count()).group_by(col).order_by(func.count().desc(), col)).all()
        data[column] = [{"value": v, "count": n} for v, n in rows]
    data["total"] = db.session.scalar(select(func.count()).select_from(Person))
    return ok(data)
