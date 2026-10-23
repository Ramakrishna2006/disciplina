"""System endpoints. /api/health is what Render (and you) call to check the server is alive."""
from flask import Blueprint, current_app
from sqlalchemy import text

from ..extensions import db
from ..utils.responses import ok

bp = Blueprint("system", __name__, url_prefix="/api")


@bp.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001 - any failure means "database unreachable"
        current_app.logger.exception("health check: database unreachable")
        db.session.rollback()
        database = "unreachable"
    cfg = current_app.config
    data = {"status": "ok" if database == "ok" else "degraded", "database": database,
            "app": cfg["APP_NAME"], "version": cfg["VERSION"], "environment": cfg["ENV_NAME"],
            "training_enabled": cfg["TRAINING_ENABLED"]}
    return ok(data, 200 if database == "ok" else 503)
