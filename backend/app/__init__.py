"""
Disciplina Studio backend: the application factory.

    flask --app backend.app run          (development server, from the repository folder)
    gunicorn backend.wsgi:app            (production, on Render)

create_app() builds a fresh, fully configured app each time it is called. Tests call it with
"testing" to get an app with its own temporary database.
"""
import sys

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from ..config import ROOT_DIR, check_production, get_config
from .extensions import db, jwt, limiter, migrate

# The engine lives in llm/ at the repository root; make sure `import llm` always works.
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))


def create_app(config_name=None, **overrides):
    config = get_config(config_name)
    app = Flask(__name__, instance_path=str(ROOT_DIR / "backend" / "instance"), static_folder=None)
    app.config.from_object(config)
    app.config.update(overrides)
    if app.config["ENV_NAME"] == "production":
        check_production(config)
    app.json.sort_keys = False
    if app.config["TRUST_PROXY"]:
        # Behind Render's proxy: read the real client IP (for rate limits) and https from its headers.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)

    db.init_app(app)
    migrate.init_app(app, db, directory=str(ROOT_DIR / "backend" / "migrations"),
                     render_as_batch=True)   # lets migrations change columns on SQLite too
    jwt.init_app(app)
    limiter.init_app(app)

    from . import models  # noqa: F401  (registers every table with SQLAlchemy and Alembic)
    from .cli import register_cli
    from .routes import BLUEPRINTS
    from .services.auth import register_jwt_callbacks
    from .services.jobs import init_jobs
    from .utils.errors import register_error_handlers
    from .utils.security import register_request_logging, register_security

    for bp in BLUEPRINTS:
        app.register_blueprint(bp)
    register_jwt_callbacks()
    register_error_handlers(app)
    register_security(app)
    register_request_logging(app)
    register_cli(app)
    init_jobs(app)
    return app
