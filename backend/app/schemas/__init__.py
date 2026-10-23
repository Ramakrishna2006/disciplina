"""
Request validation with Pydantic. Each schema says exactly which fields a request may send,
their types and their limits. `parse(Schema)` reads the JSON body and either returns a clean,
typed object or answers 400 with a message for every bad field:

    {"error": {"code": "validation_error", "message": "...", "fields": {"password": "..."}}}
"""
from flask import request
from pydantic import BaseModel, ConfigDict, ValidationError

from ..utils.errors import ApiError


class Schema(BaseModel):
    # forbid: an unexpected field (e.g. "role": "admin" on register) is an error, never silently used
    model_config = ConfigDict(extra="forbid")


def _field_message(err):
    msg = err["msg"]
    for prefix in ("Value error, ", "Assertion failed, "):
        msg = msg.removeprefix(prefix)
    return msg[:1].upper() + msg[1:]


def parse(schema):
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError(400, "Send the request body as a JSON object.", code="bad_request")
    try:
        return schema.model_validate(data)
    except ValidationError as e:
        fields = {}
        for err in e.errors(include_url=False):
            name = ".".join(str(p) for p in err["loc"]) or "body"
            fields.setdefault(name, "This field is not allowed." if err["type"] == "extra_forbidden"
                              else _field_message(err))
        raise ApiError(400, "Please check the highlighted fields.", code="validation_error", fields=fields) from None
