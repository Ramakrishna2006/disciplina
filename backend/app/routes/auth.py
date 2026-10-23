"""
/api/auth: register, login, refresh, logout, me.

Change requests need the X-CSRF-TOKEN header (copied by the frontend from the csrf_access_token
cookie, or csrf_refresh_token for /refresh). Register and login are the exceptions: there is no
session yet, and SameSite=Lax cookies stop other sites from using a session they create.
"""
from flask import Blueprint, current_app
from flask_jwt_extended import (create_access_token, current_user, get_jwt_identity, jwt_required,
                                set_access_cookies)

from ..extensions import db, limiter
from ..models import User
from ..schemas import parse
from ..schemas.auth import LoginIn, RegisterIn
from ..services import auth as auth_service
from ..utils.errors import ApiError

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/register")
@limiter.limit(lambda: current_app.config["RATELIMIT_REGISTER"])
def register():
    body = parse(RegisterIn)
    if db.session.query(User.id).filter_by(email=body.email).first():
        raise ApiError(409, "An account with this email already exists. Try signing in.", code="email_taken",
                       fields={"email": "This email is already registered."})
    user = User(email=body.email, name=body.name)   # role is always "member": never taken from the request
    user.set_password(body.password)
    auth_service.mark_login(user)
    db.session.add(user)
    db.session.commit()
    return auth_service.issue_tokens(auth_service.json_response({"user": user.to_dict()}, 201), user)


@bp.post("/login")
@limiter.limit(lambda: current_app.config["RATELIMIT_LOGIN"])
def login():
    body = parse(LoginIn)
    user = auth_service.verify_login(body.email, body.password)
    if user is None:
        # One message for "no such email" and "wrong password": never reveal which accounts exist.
        raise ApiError(401, "Wrong email or password.", code="invalid_credentials")
    if not user.is_active:
        raise ApiError(403, "This account is disabled.", code="account_disabled")
    auth_service.mark_login(user)
    db.session.commit()
    return auth_service.issue_tokens(auth_service.json_response({"user": user.to_dict()}), user)


@bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    """The access token lasts 30 minutes; the 7-day refresh token gets a new one without a password."""
    response = auth_service.json_response({"user": current_user.to_dict()})
    set_access_cookies(response, create_access_token(identity=get_jwt_identity()))
    return response


@bp.post("/logout")
def logout():
    """Works even with an expired access token, so you can always sign out. The CSRF header is
    still required when a session is present, so another website cannot sign you out."""
    claims = auth_service.request_token_claims()
    if claims:
        if not auth_service.csrf_matches(claims):
            raise ApiError(401, "Your session could not be verified. Refresh the page and try again.",
                           code="csrf_failed")
        auth_service.revoke(claims)
        db.session.commit()
    return auth_service.clear_tokens(auth_service.json_response({"signed_out": True}))


@bp.get("/me")
@jwt_required()
def me():
    return auth_service.json_response({"user": current_user.to_dict()})
