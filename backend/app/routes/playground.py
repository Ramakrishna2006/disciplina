"""
The Playground and the tools that look inside the model:

    POST   /api/chat                    ask a model; the conversation is saved
    GET    /api/chat/sessions           your saved conversations, newest first
    GET    /api/chat/sessions/<id>      one conversation with its messages
    PATCH  /api/chat/sessions/<id>      rename it
    DELETE /api/chat/sessions/<id>      delete it
    POST   /api/tokenize                how the tokenizer splits a text
    GET    /api/embeddings              the 2-D map of city, job and food words
    GET    /api/embeddings/neighbors    the words closest to one word
"""
from flask import Blueprint, current_app
from flask_jwt_extended import current_user, get_jwt_identity, jwt_required
from sqlalchemy import func, select

from ..extensions import db, limiter
from ..models import ChatMessage, ChatSession
from ..models.base import utcnow
from ..schemas import parse, parse_query
from ..schemas.studio import ChatIn, EmbeddingsQuery, NeighborsQuery, Page, SessionPatchIn, TokenizeIn
from ..services.engine import EngineUnavailable, get_engine
from ..utils.errors import ApiError
from ..utils.pagination import paginate
from ..utils.responses import ok

bp = Blueprint("playground", __name__, url_prefix="/api")


def engine():
    e = get_engine()
    try:
        e.load()
    except EngineUnavailable as err:
        current_app.logger.error("%s", err)
        raise ApiError(503, "The trained models are not available on this server.", code="models_unavailable") from None
    return e


def own_session(session_id):
    """Your conversation, or 404. Someone else's conversation is also "not found", so ids reveal nothing."""
    s = db.session.get(ChatSession, session_id)
    if s is None or s.user_id != current_user.id:
        raise ApiError(404, "Conversation not found.")
    return s


# ------------------------------------------------------------------ chat
@bp.post("/chat")
@jwt_required()
@limiter.limit(lambda: current_app.config["RATELIMIT_CHAT"], key_func=lambda: f"user:{get_jwt_identity()}")
def chat():
    body = parse(ChatIn)
    session = own_session(body.session_id) if body.session_id else None
    reply, tokens, ms = engine().reply(body.model, body.message, body.temperature, body.top_k)
    if session is None:
        title = body.message if len(body.message) <= 60 else body.message[:57].rstrip() + "..."
        session = ChatSession(user_id=current_user.id, title=title, model=body.model)
        db.session.add(session)
    session.model = body.model
    settings = {"model": body.model, "temperature": body.temperature, "top_k": body.top_k}
    question = ChatMessage(role="user", content=body.message, **settings)
    answer = ChatMessage(role="assistant", content=reply, latency_ms=ms, **settings)
    session.messages.extend([question, answer])
    session.updated_at = utcnow()          # newest conversation first in the list
    db.session.commit()
    return ok({"session_id": session.id, "reply": reply, "latency_ms": ms, "tokens": tokens,
               "messages": [question.to_dict(), answer.to_dict()]})


@bp.get("/chat/sessions")
@jwt_required()
def list_sessions():
    q = parse_query(Page)
    stmt = (select(ChatSession).where(ChatSession.user_id == current_user.id)
            .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc()))
    sessions, meta = paginate(stmt, q.page, q.per_page)
    ids = [s.id for s in sessions]
    counts = dict(db.session.execute(select(ChatMessage.session_id, func.count())
                                     .where(ChatMessage.session_id.in_(ids)).group_by(ChatMessage.session_id)).all())
    last_ids = select(func.max(ChatMessage.id)).where(ChatMessage.session_id.in_(ids)).group_by(ChatMessage.session_id)
    last = {m.session_id: m.content for m in db.session.scalars(select(ChatMessage).where(ChatMessage.id.in_(last_ids)))}
    return ok([s.to_dict(counts.get(s.id, 0), last.get(s.id)) for s in sessions], meta=meta)


@bp.get("/chat/sessions/<int:session_id>")
@jwt_required()
def get_session(session_id):
    s = own_session(session_id)
    return ok({"session": s.to_dict(len(s.messages), s.messages[-1].content if s.messages else None),
               "messages": [m.to_dict() for m in s.messages]})


@bp.patch("/chat/sessions/<int:session_id>")
@jwt_required()
def rename_session(session_id):
    s = own_session(session_id)
    s.title = parse(SessionPatchIn).title
    db.session.commit()
    return ok({"session": s.to_dict()})


@bp.delete("/chat/sessions/<int:session_id>")
@jwt_required()
def delete_session(session_id):
    db.session.delete(own_session(session_id))
    db.session.commit()
    return "", 204


# ------------------------------------------------------------------ tokenizer and embeddings
@bp.post("/tokenize")
@jwt_required()
def tokenize():
    text = parse(TokenizeIn).text
    tokens = engine().tokenize(text)
    return ok({"tokens": tokens, "count": len(tokens), "characters": len(text),
               "chars_per_token": round(len(text) / len(tokens), 2) if tokens else 0})


@bp.get("/embeddings")
@jwt_required()
def embeddings():
    q = parse_query(EmbeddingsQuery)
    return ok({"model": q.model, "points": engine().embedding_points(q.model)})


@bp.get("/embeddings/neighbors")
@jwt_required()
def neighbors():
    q = parse_query(NeighborsQuery)
    word = q.word.strip()
    found = engine().neighbors(word, q.k, q.model)
    if found is None:
        raise ApiError(404, f"\"{word}\" is not a single token, so it has no embedding of its own. "
                            "Try a city, job or food from the dataset.", code="not_a_token")
    return ok({"word": word, "model": q.model, "neighbors": found})
