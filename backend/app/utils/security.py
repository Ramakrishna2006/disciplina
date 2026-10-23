"""Security headers on every response, and one log line per request."""
import logging
import time

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
    def _start_timer():
        g.request_started = time.perf_counter()

    @app.after_request
    def _log(response):
        ms = (time.perf_counter() - g.get("request_started", time.perf_counter())) * 1000
        # Method, path and status only: never bodies, passwords or tokens.
        log.info("%s %s %s %.0fms", request.method, request.path, response.status_code, ms)
        return response
