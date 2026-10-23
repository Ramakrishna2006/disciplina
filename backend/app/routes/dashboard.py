"""
The Dashboard, the Activity page and the bell, and the app settings the frontend needs.

    GET  /api/dashboard        your numbers, the latest loss curve, recent activity
    GET  /api/activity         your activity, newest first (?unread=true for unread only)
    POST /api/activity/read    mark some (ids) or all of it as read
    GET  /api/config           presets, limits, models, whether training is on (no sign-in needed)
"""
from flask import Blueprint, current_app
from flask_jwt_extended import current_user, jwt_required
from sqlalchemy import func, or_, select, update

from ..extensions import db
from ..models import ActivityEvent, ChatMessage, ChatSession, Experiment, Metric, Result
from ..models.base import utcnow
from ..models.experiment import ACTIVE, LIMITS
from ..schemas import parse, parse_query
from ..schemas.studio import ActivityQuery, ActivityReadIn
from ..services.engine import MODEL_INFO
from ..utils.pagination import paginate
from ..utils.responses import ok

bp = Blueprint("dashboard", __name__, url_prefix="/api")
PRESET_MINUTES = {"quick": "4-7", "short": "8-12", "full": "30-40"}   # on a laptop CPU


def count(stmt):
    return db.session.scalar(select(func.count()).select_from(stmt.subquery()))


def unread_count():
    return count(select(ActivityEvent.id).where(ActivityEvent.user_id == current_user.id,
                                                ActivityEvent.read_at.is_(None)))


@bp.get("/dashboard")
@jwt_required()
def dashboard():
    me = current_user.id
    mine = select(Experiment.id).where(Experiment.owner_id == me)
    kpis = {
        "experiments": count(mine),
        "completed": count(mine.where(Experiment.status == "completed")),
        "active": count(mine.where(Experiment.status.in_(ACTIVE))),
        "chats": count(select(ChatSession.id).where(ChatSession.user_id == me)),
        "questions": count(select(ChatMessage.id).join(ChatSession)
                           .where(ChatSession.user_id == me, ChatMessage.role == "user")),
        "best_heldout": db.session.scalar(
            select(func.max(Result.qa_heldout)).join(Experiment)
            .where(or_(Experiment.owner_id == me, Experiment.is_public.is_(True)))),
    }
    # The loss curve of your latest finished experiment, or else the published reference run.
    visible = or_(Experiment.owner_id == me, Experiment.is_public.is_(True))
    latest = db.session.scalar(
        select(Experiment).where(visible, Experiment.status == "completed")
        .order_by((Experiment.owner_id == me).desc(), Experiment.finished_at.desc(), Experiment.id.desc()).limit(1))
    curve = None
    if latest is not None:
        rows = db.session.scalars(select(Metric).where(Metric.experiment_id == latest.id, Metric.phase == "pretrain")
                                  .order_by(Metric.step)).all()
        curve = {"experiment": latest.to_dict(owner=latest.owner_id == me),
                 "metrics": [m.to_dict() for m in rows]}
    active = db.session.scalar(select(Experiment).where(Experiment.owner_id == me, Experiment.status.in_(ACTIVE))
                               .order_by(Experiment.id.desc()).limit(1))
    recent = db.session.scalars(select(ActivityEvent).where(ActivityEvent.user_id == me)
                                .order_by(ActivityEvent.id.desc()).limit(5)).all()
    return ok({"kpis": kpis, "latest": curve,
               "active_experiment": active.to_dict(owner=True, results=False) if active else None,
               "activity": [e.to_dict() for e in recent], "unread": unread_count()})


@bp.get("/activity")
@jwt_required()
def activity():
    q = parse_query(ActivityQuery)
    stmt = select(ActivityEvent).where(ActivityEvent.user_id == current_user.id)
    if q.unread:
        stmt = stmt.where(ActivityEvent.read_at.is_(None))
    events, meta = paginate(stmt.order_by(ActivityEvent.id.desc()), q.page, q.per_page)
    meta["unread"] = unread_count()
    return ok([e.to_dict() for e in events], meta=meta)


@bp.post("/activity/read")
@jwt_required()
def mark_read():
    body = parse(ActivityReadIn)
    stmt = update(ActivityEvent).where(ActivityEvent.user_id == current_user.id, ActivityEvent.read_at.is_(None))
    if body.ids is not None:
        stmt = stmt.where(ActivityEvent.id.in_(body.ids))     # only your own events, whatever ids are sent
    changed = db.session.execute(stmt.values(read_at=utcnow())).rowcount
    db.session.commit()
    return ok({"marked": changed, "unread": unread_count()})


@bp.get("/config")
def app_config():
    from llm.experiment import PRESETS

    cfg = current_app.config
    presets = [{"name": name, "pretrain_steps": p.pretrain_steps, "finetune_steps": p.finetune_steps,
                "minutes": PRESET_MINUTES.get(name)} for name, p in PRESETS.items()]
    presets.sort(key=lambda p: p["pretrain_steps"])
    return ok({"app": cfg["APP_NAME"], "version": cfg["VERSION"], "training_enabled": cfg["TRAINING_ENABLED"],
               "presets": presets,
               "limits": {**{k: {"min": lo, "max": hi} for k, (lo, hi) in LIMITS.items()},
                          "seed": {"min": 0, "max": 9999}, "message": {"max": 500}, "tokenize": {"max": 1000},
                          "temperature": {"min": 0, "max": 2}, "top_k": {"min": 1, "max": 100}},
               "models": [{"id": k, **v} for k, v in MODEL_INFO.items()]})
