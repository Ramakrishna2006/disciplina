"""/api/users/me: your profile, your password, deleting your account. Always the signed-in user:
there is no user id in these URLs, so nobody can change someone else's account."""
from flask import Blueprint, current_app
from flask_jwt_extended import current_user, jwt_required

from ..extensions import db
from ..models import User
from ..schemas import parse
from ..schemas.auth import DeleteAccountIn, PasswordChangeIn, ProfileIn
from ..services import auth as auth_service
from ..utils.errors import ApiError

bp = Blueprint("users", __name__, url_prefix="/api/users")


@bp.patch("/me")
@jwt_required()
def update_profile():
    body = parse(ProfileIn)
    for field in body.model_fields_set:          # only the fields that were sent
        setattr(current_user, field, getattr(body, field))
    db.session.commit()
    return auth_service.json_response({"user": current_user.to_dict()})


@bp.post("/me/password")
@jwt_required()
def change_password():
    body = parse(PasswordChangeIn)
    if not current_user.check_password(body.current_password):
        raise ApiError(400, "Your current password is not correct.", code="validation_error",
                       fields={"current_password": "Incorrect password."})
    if body.new_password == body.current_password:
        raise ApiError(400, "Choose a password you have not used here before.", code="validation_error",
                       fields={"new_password": "Must be different from the current password."})
    current_user.set_password(body.new_password)
    auth_service.logout_everywhere(current_user)          # other devices are signed out ...
    auth_service.revoke(auth_service.request_token_claims())
    db.session.commit()
    response = auth_service.json_response({"user": current_user.to_dict()})
    return auth_service.issue_tokens(response, current_user)   # ... and this one gets new tokens


@bp.delete("/me")
@jwt_required()
def delete_account():
    body = parse(DeleteAccountIn)
    if not current_user.check_password(body.password):
        raise ApiError(400, "Your password is not correct.", code="validation_error",
                       fields={"password": "Incorrect password."})
    auth_service.revoke(auth_service.request_token_claims())
    # The database deletes everything the user owns (ON DELETE CASCADE): experiments, metrics,
    # results, chats and activity. One statement, one transaction.
    db.session.execute(db.delete(User).where(User.id == current_user.id))
    db.session.commit()
    return auth_service.clear_tokens(current_app.response_class(status=204))   # 204: success, no body
