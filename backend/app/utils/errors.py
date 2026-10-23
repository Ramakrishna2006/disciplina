"""
Every API error has the same shape, so the frontend handles them all in one place:

    {"error": {"code": "not_found", "message": "Experiment not found.", "fields": {}}}

`code` is stable and meant for programs; `message` is a sentence for people; `fields` maps form
field names to problems (filled for validation errors).
"""
from flask import jsonify, request
from werkzeug.exceptions import HTTPException

from ..extensions import db

CODES = {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found",
         405: "method_not_allowed", 409: "conflict", 413: "payload_too_large", 415: "unsupported_media_type",
         422: "validation_error", 429: "rate_limited", 500: "server_error", 503: "unavailable"}


class ApiError(Exception):
    """Raise anywhere in a request: `raise ApiError(404, "Experiment not found.")`."""

    def __init__(self, status, message, code=None, fields=None):
        super().__init__(message)
        self.status, self.message = status, message
        self.code = code or CODES.get(status, "error")
        self.fields = fields or {}


def error_response(status, message, code=None, fields=None):
    body = {"error": {"code": code or CODES.get(status, "error"), "message": message, "fields": fields or {}}}
    return jsonify(body), status


def register_error_handlers(app):
    @app.errorhandler(ApiError)
    def _api_error(err):
        db.session.rollback()   # never leave a half-finished change behind
        return error_response(err.status, err.message, err.code, err.fields)

    @app.errorhandler(HTTPException)
    def _http_error(err):
        # JSON for the API; the normal HTML page for anything else (the React app handles its own 404s)
        if request.path.startswith("/api"):
            return error_response(err.code, err.description)
        return err

    @app.errorhandler(Exception)
    def _unexpected(err):
        db.session.rollback()
        app.logger.exception("unhandled error on %s %s", request.method, request.path)
        # The details go to the server log only; the user never sees code or stack traces.
        return error_response(500, "Something went wrong on the server. Please try again.")
