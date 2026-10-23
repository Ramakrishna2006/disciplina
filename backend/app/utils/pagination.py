"""Pages of results: `items, meta = paginate(query, page, per_page)`.

meta is {"page": 2, "per_page": 20, "total": 57, "pages": 3}; the frontend uses it for the
"Previous / Next" buttons. A page after the last one is simply empty (not an error)."""
from sqlalchemy import func, select

from ..extensions import db


def paginate(stmt, page, per_page):
    total = db.session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    items = db.session.scalars(stmt.limit(per_page).offset((page - 1) * per_page)).all()
    return items, {"page": page, "per_page": per_page, "total": total,
                   "pages": max(1, -(-total // per_page))}
