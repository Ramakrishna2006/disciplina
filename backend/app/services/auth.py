"""
Login tokens: creating them, checking them, revoking them.

A JWT (JSON Web Token) is a small signed note: "user 7, token id abc, expires 14:30". The
server signs it with JWT_SECRET_KEY, so nobody can forge or edit one. We keep tokens in
httpOnly cookies (JavaScript cannot read them) and check on every request that the token:
  * is correctly signed and not expired          (Flask-JWT-Extended does this)
  * was not logged out: its id is not in token_blocklist
  * was issued after the user's last password change (users.tokens_valid_after)
  * belongs to a user who still exists and is active
"""
import hmac
from datetime import datetime, timezone

from flask import current_app, jsonify, request
from flask_jwt_extended import (create_access_token, create_refresh_token, decode_token,
                                set_access_cookies, set_refresh_cookies, unset_jwt_cookies)
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db, jwt
from ..models import TokenBlocklist, User
from ..models.base import utcnow
from ..utils.errors import error_response

_DUMMY_HASH = None


def verify_login(email, password):
    """The user if the email and password match, else None. An unknown email costs the same time
    as a wrong password, so response times do not reveal which emails have accounts."""
    global _DUMMY_HASH
    user = db.session.query(User).filter_by(email=email).one_or_none()
    if user is None:
        _DUMMY_HASH = _DUMMY_HASH or generate_password_hash("not-a-real-password")
        check_password_hash(_DUMMY_HASH, password)
        return None
    return user if user.check_password(password) else None


def issue_tokens(response, user):
    """Put a fresh access token and refresh token (and their CSRF cookies) on the response."""
    identity = str(user.id)
    set_access_cookies(response, create_access_token(identity=identity))
    set_refresh_cookies(response, create_refresh_token(identity=identity))
    return response


def request_token_claims():
    """The contents of the access and refresh cookies this browser sent, including expired ones.
    Unreadable or forged cookies are skipped: they prove nothing and can only be cleared."""
    claims = []
    for cookie in (current_app.config["JWT_ACCESS_COOKIE_NAME"], current_app.config["JWT_REFRESH_COOKIE_NAME"]):
        token = request.cookies.get(cookie)
        if token:
            try:
                claims.append(decode_token(token, allow_expired=True))
            except Exception:  # noqa: BLE001
                pass
    return claims


def csrf_matches(claims):
    """The X-CSRF-TOKEN header must equal the CSRF value inside one of the tokens (double submit)."""
    header = request.headers.get(current_app.config["JWT_ACCESS_CSRF_HEADER_NAME"], "")
    return bool(header) and any(hmac.compare_digest(header, c.get("csrf", "")) for c in claims)


def revoke(claims):
    """Put token ids on the blocklist, so copies of those tokens can never be used again."""
    for c in claims:
        if not db.session.query(TokenBlocklist.id).filter_by(jti=c["jti"]).first():
            db.session.add(TokenBlocklist(jti=c["jti"]))


def clear_tokens(response):
    unset_jwt_cookies(response)
    return response


def register_jwt_callbacks():
    @jwt.user_lookup_loader
    def _load_user(_header, payload):
        # `current_user` in routes. None (deleted or disabled account) answers 401.
        user = db.session.get(User, int(payload["sub"]))
        return user if user is not None and user.is_active else None

    @jwt.token_in_blocklist_loader
    def _is_revoked(_header, payload):
        if db.session.query(TokenBlocklist.id).filter_by(jti=payload["jti"]).first():
            return True
        user = db.session.get(User, int(payload["sub"]))
        if user is not None and user.tokens_valid_after is not None:
            issued = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
            return issued < user.tokens_valid_after.replace(microsecond=0)
        return False

    # Every failure answers in our JSON error format, with a code the frontend can act on.
    @jwt.unauthorized_loader
    def _missing(reason):
        if "CSRF" in reason:
            return error_response(401, "Your session could not be verified. Refresh the page and try again.",
                                  code="csrf_failed")
        return error_response(401, "Please sign in.", code="not_signed_in")

    @jwt.expired_token_loader
    def _expired(_header, _payload):
        return error_response(401, "Your session has expired.", code="token_expired")

    @jwt.invalid_token_loader
    def _invalid(_reason):
        return error_response(401, "Please sign in again.", code="invalid_token")

    @jwt.revoked_token_loader
    def _revoked(_header, _payload):
        return error_response(401, "You have been signed out. Please sign in again.", code="token_revoked")

    @jwt.user_lookup_error_loader
    def _no_user(_header, _payload):
        return error_response(401, "This account is no longer available.", code="account_unavailable")


def mark_login(user):
    user.last_login_at = utcnow()


def logout_everywhere(user):
    """Refuse every token issued before now (used on password change)."""
    user.tokens_valid_after = utcnow()


def json_response(data, status=200):
    """A response object we can still attach cookies to."""
    response = jsonify({"data": data})
    response.status_code = status
    return response
