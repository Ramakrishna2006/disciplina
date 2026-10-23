"""Security headers on every response, and one log line per request."""
import logging
import re
import time
import uuid

from flask import g, request

CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
       "script-src 'self'; connect-src 'self'; font-src 'self' data:; object-src 'none'; "
       "base-uri 'self'; form-action 'self'; frame-ancestors 'none'")


def register_security(app):
    @app.after_request
    def _headers(response):
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")        # browsers must not guess file types
        h.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        h.setdefault("X-Frame-Options", "DENY")                  # no embedding in other sites (clickjacking)
        h.setdefault("Content-Security-Policy", CSP)             # only our own scripts may run
        h.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if request.path.startswith("/api"):
            h.setdefault("Cache-Control", "no-store")            # API answers may be private
        if app.config.get("ENV_NAME") == "production":
            h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


def register_request_logging(app):
    logging.basicConfig(level=app.config.get("LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app.logger.setLevel(app.config.get("LOG_LEVEL", "INFO"))
    log = logging.getLogger("disciplina.request")

    @app.before_request
    def _start_request():
        g.request_started = time.perf_counter()
        # A short id for this request: shown in error messages and every log line, so a user's
        # "error abc123" can be found in the server log. Render's own id is reused when present.
        incoming = request.headers.get("X-Request-ID", "")
        g.request_id = incoming if re.fullmatch(r"[A-Za-z0-9-]{8,64}", incoming) else uuid.uuid4().hex[:12]

    @app.after_request
    def _log(response):
        ms = (time.perf_counter() - g.get("request_started", time.perf_counter())) * 1000
        response.headers.setdefault("X-Request-ID", g.get("request_id", "-"))
        # Method, path and status only: never bodies, passwords or tokens.
        log.info("[%s] %s %s %s %.0fms", g.get("request_id", "-"), request.method, request.path,
                 response.status_code, ms)
        return response
