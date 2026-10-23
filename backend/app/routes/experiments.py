"""
Experiments: train the whole recipe with your own settings and compare the results.

    GET    /api/experiments                   yours (scope=mine) or everyone's published ones (scope=public)
    POST   /api/experiments                   queue a new one (202)
    GET    /api/experiments/compare?ids=1,2   2 to 4 side by side
    GET    /api/experiments/<id>              one experiment with its scores
    PATCH  /api/experiments/<id>              rename, describe, publish (admins only)
    DELETE /api/experiments/<id>              delete (not while it is running)
    POST   /api/experiments/<id>/cancel       stop it (queued: at once; running: within a second)
    GET    /api/experiments/<id>/metrics      the loss curves; ?after_id=N returns only newer points
    GET    /api/experiments/<id>/log          the last lines of the training log
    GET    /api/experiments/<id>/export.csv   the loss curves as a spreadsheet file

You can see your own experiments and published ones. Anyone else's private experiment answers
404 "not found", exactly like one that does not exist.
"""
import csv
import io

from flask import Blueprint, Response, current_app
from flask_jwt_extended import current_user, get_jwt_identity, jwt_required
from sqlalchemy import case, func, or_, select

from ..extensions import db, limiter
from ..models import Experiment, Metric, Result
from ..models.base import utcnow
from ..models.experiment import ACTIVE
from ..schemas import parse, parse_query
from ..schemas.studio import CompareQuery, ExperimentIn, ExperimentPatchIn, ExperimentsQuery, MetricsQuery
from ..services import jobs
from ..utils.errors import ApiError
from ..utils.pagination import paginate
from ..utils.responses import ok

bp = Blueprint("experiments", __name__, url_prefix="/api/experiments")
METRICS_PAGE = 5000


def is_admin():
    return current_user.role == "admin"


def visible(exp_id):
    exp = db.session.get(Experiment, exp_id)
    if exp is None or not (exp.is_public or exp.owner_id == current_user.id or is_admin()):
        raise ApiError(404, "Experiment not found.")
    return exp


def owned(exp_id):
    """Change and delete: only the owner (or an admin). Seeing a published one is not enough."""
    exp = visible(exp_id)
    if exp.owner_id != current_user.id and not is_admin():
        raise ApiError(403, "Only the owner can change this experiment.")
    return exp


def as_dict(exp, **kw):
    return exp.to_dict(owner=exp.owner_id == current_user.id, **kw)


@bp.get("")
@jwt_required()
def list_experiments():
    q = parse_query(ExperimentsQuery)
    stmt = select(Experiment)
    stmt = stmt.where(Experiment.is_public.is_(True)) if q.scope == "public" else \
        stmt.where(Experiment.owner_id == current_user.id)
    if q.status:
        stmt = stmt.where(Experiment.status == q.status)
    if q.replay is not None:
        stmt = stmt.where(Experiment.replay.is_(q.replay))
    if q.search:
        like = "%" + q.search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        stmt = stmt.where(or_(Experiment.name.ilike(like, escape="\\"), Experiment.description.ilike(like, escape="\\")))
    if q.sort == "qa_heldout":
        score = (select(Result.qa_heldout).where(Result.experiment_id == Experiment.id, Result.model == "lora")
                 .correlate(Experiment).scalar_subquery())
        col = func.coalesce(score, -1)
    else:
        col = getattr(Experiment, q.sort)
    stmt = stmt.order_by(col.desc() if q.order == "desc" else col.asc(), Experiment.id.desc())
    items, meta = paginate(stmt, q.page, q.per_page)
    return ok([as_dict(e) for e in items], meta=meta)


@bp.post("")
@jwt_required()
@limiter.limit(lambda: current_app.config["RATELIMIT_EXPERIMENTS"], key_func=lambda: f"user:{get_jwt_identity()}")
def create_experiment():
    if not current_app.config["TRAINING_ENABLED"]:
        raise ApiError(403, "Training is switched off on this server. Run Disciplina Studio on your own "
                            "computer to train experiments.", code="training_disabled")
    body = parse(ExperimentIn)
    busy = db.session.scalar(select(Experiment.id).where(Experiment.owner_id == current_user.id,
                                                         Experiment.status.in_(ACTIVE)).limit(1))
    if busy:
        raise ApiError(409, "You already have an experiment queued or training. Wait for it to finish, "
                            "or cancel it.", code="experiment_active")
    exp = Experiment(owner_id=current_user.id, **body.model_dump())
    db.session.add(exp)
    db.session.commit()
    jobs.wake()
    ahead = db.session.scalar(select(func.count()).select_from(Experiment)
                              .where(Experiment.status.in_(ACTIVE), Experiment.id < exp.id))
    return ok({"experiment": as_dict(exp)}, 202, meta={"queue_position": ahead + 1})


@bp.get("/compare")
@jwt_required()
def compare():
    ids = parse_query(CompareQuery).ids
    exps = [visible(i) for i in ids]
    curves = {}
    for exp in exps:
        rows = db.session.scalars(select(Metric).where(Metric.experiment_id == exp.id).order_by(Metric.id)).all()
        curves[exp.id] = [m.to_dict() for m in rows]
    return ok({"experiments": [as_dict(e) for e in exps], "metrics": {str(k): v for k, v in curves.items()}})


@bp.get("/<int:exp_id>")
@jwt_required()
def get_experiment(exp_id):
    exp = visible(exp_id)
    data = {"experiment": as_dict(exp)}
    if exp.status == "queued":
        data["queue_position"] = 1 + db.session.scalar(select(func.count()).select_from(Experiment)
                                                       .where(Experiment.status.in_(ACTIVE), Experiment.id < exp.id))
    return ok(data)


@bp.patch("/<int:exp_id>")
@jwt_required()
def update_experiment(exp_id):
    exp = owned(exp_id)
    body = parse(ExperimentPatchIn)
    if "is_public" in body.model_fields_set and not is_admin():
        raise ApiError(403, "Only an admin can publish experiments.", code="admin_only")
    if "is_public" in body.model_fields_set and body.is_public and exp.status != "completed":
        raise ApiError(409, "Only a completed experiment can be published.", code="not_completed")
    for field in body.model_fields_set:
        value = getattr(body, field)
        if value is None:
            raise ApiError(400, "Please check the highlighted fields.", code="validation_error",
                           fields={field: "This field cannot be empty."})
        setattr(exp, field, value)
    db.session.commit()
    return ok({"experiment": as_dict(exp)})


@bp.delete("/<int:exp_id>")
@jwt_required()
def delete_experiment(exp_id):
    exp = owned(exp_id)
    if exp.status == "running":
        raise ApiError(409, "This experiment is training. Cancel it first, then delete it.", code="experiment_running")
    db.session.delete(exp)
    db.session.commit()
    jobs.delete_run_files(exp_id)          # the trained model files, if any
    return "", 204


@bp.post("/<int:exp_id>/cancel")
@jwt_required()
def cancel_experiment(exp_id):
    exp = owned(exp_id)
    if exp.status == "queued":
        exp.status, exp.finished_at, exp.cancel_requested = "cancelled", utcnow(), True
        jobs.add_event(exp, "experiment.cancelled", f"\"{exp.name}\" was cancelled.")
    elif exp.status == "running":
        exp.cancel_requested = True        # the runner notices within a second and stops
    else:
        raise ApiError(409, f"This experiment is already {exp.status}.", code="not_active")
    db.session.commit()
    return ok({"experiment": as_dict(exp)})


@bp.get("/<int:exp_id>/metrics")
@jwt_required()
def metrics(exp_id):
    exp = visible(exp_id)
    after = parse_query(MetricsQuery).after_id
    rows = db.session.scalars(select(Metric).where(Metric.experiment_id == exp.id, Metric.id > after)
                              .order_by(Metric.id).limit(METRICS_PAGE)).all()
    # Validation losses are added to existing pre-training points when the run finishes, so a
    # finished run's page asks once more from 0 to get them (meta.complete tells it when).
    return ok([m.to_dict() for m in rows],
              meta={"last_id": rows[-1].id if rows else after, "status": exp.status,
                    "progress": round(exp.progress, 4), "phase": exp.phase,
                    "complete": not exp.active})


@bp.get("/<int:exp_id>/log")
@jwt_required()
def run_log(exp_id):
    exp = visible(exp_id)
    path = jobs.run_dir(exp.id) / "run_log.txt"
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()[-200:] if path.is_file() else []
    return ok({"lines": lines})


@bp.get("/<int:exp_id>/export.csv")
@jwt_required()
def export_csv(exp_id):
    exp = visible(exp_id)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["phase", "step", "train_loss", "val_loss"])
    phase_order = case({"pretrain": 0, "full": 1, "lora": 2}, value=Metric.phase)
    for m in db.session.scalars(select(Metric).where(Metric.experiment_id == exp.id)
                                .order_by(phase_order, Metric.step)):
        w.writerow([m.phase, m.step, f"{m.train_loss:.5f}", "" if m.val_loss is None else f"{m.val_loss:.5f}"])
    if exp.results:
        w.writerow([])
        w.writerow(["model", "qa_seen", "qa_heldout", "completion", "perplexity", "trainable_params"])
        for r in exp.results:
            w.writerow([r.model, r.qa_seen, r.qa_heldout, r.completion, f"{r.perplexity:.4f}", r.trainable_params])
    safe = "".join(c if c.isalnum() else "-" for c in exp.name.lower()).strip("-")[:40] or "experiment"
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="experiment-{exp.id}-{safe}.csv"'})
