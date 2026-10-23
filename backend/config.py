"""
Settings for the Disciplina Studio backend.

Three profiles, chosen with the FLASK_CONFIG environment variable:
  development (default)  your laptop: SQLite file, a secret key created for you, debug logging
  testing                pytest: a temporary database, nothing written to backend/instance
  production             Render: every secret must come from environment variables

Values come from environment variables, which python-dotenv loads from backend/.env
(copy backend/.env.example to start). Never put real secrets in this file.
"""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent
ROOT_DIR = BACKEND_DIR.parent                     # the repository: llm/, artifacts/, main.py
INSTANCE_DIR = BACKEND_DIR / "instance"           # local database, secret key, trained runs (git-ignored)

# Read backend/.env before the classes below look at os.environ. Real environment variables
# (set by Render, or in your terminal) win over the file.
load_dotenv(BACKEND_DIR / ".env", override=False)


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def database_url(default):
    """DATABASE_URL if set, else `default`. Hosting sites give `postgres://...`; SQLAlchemy with
    psycopg 3 needs `postgresql+psycopg://...`, so the prefix is rewritten here."""
    url = os.environ.get("DATABASE_URL", "").strip() or default
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def local_secret(name):
    """Development only: a random key created once and kept in backend/instance/<name>.
    You never have to invent a key, and it is never committed (instance/ is git-ignored)."""
    path = INSTANCE_DIR / name
    if not path.exists():
        INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(secrets.token_hex(32), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip()


class BaseConfig:
    APP_NAME = "Disciplina Studio"
    VERSION = "0.2.0"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}   # reconnect if the database slept (Neon does)
    MAX_CONTENT_LENGTH = 1 * 1024 * 1024                    # reject request bodies over 1 MB
    TRAINING_ENABLED = env_bool("TRAINING_ENABLED", True)   # false online: free hosting cannot train
    ARTIFACTS_DIR = ROOT_DIR / "artifacts"                  # the published, pre-trained models
    RUNS_DIR = INSTANCE_DIR / "experiments"                 # models trained from the web app
    LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")


class DevelopmentConfig(BaseConfig):
    ENV_NAME = "development"
    DEBUG = env_bool("FLASK_DEBUG", False)
    SQLALCHEMY_DATABASE_URI = database_url("sqlite:///" + (INSTANCE_DIR / "disciplina.db").as_posix())

    @property
    def SECRET_KEY(self):  # noqa: N802 (Flask reads upper-case names)
        return os.environ.get("SECRET_KEY") or local_secret("secret_key")


class TestingConfig(BaseConfig):
    ENV_NAME = "testing"
    TESTING = True
    SECRET_KEY = "test-only-secret-key-not-for-real-use-0123456789"
    SQLALCHEMY_DATABASE_URI = "sqlite://"                   # replaced by a temporary file in conftest.py
    TRAINING_ENABLED = True
    LOG_LEVEL = "WARNING"


class ProductionConfig(BaseConfig):
    ENV_NAME = "production"
    DEBUG = False
    SECRET_KEY = os.environ.get("SECRET_KEY", "")
    SQLALCHEMY_DATABASE_URI = database_url("")
    TRAINING_ENABLED = env_bool("TRAINING_ENABLED", False)
    PREFERRED_URL_SCHEME = "https"


CONFIGS = {"development": DevelopmentConfig, "testing": TestingConfig, "production": ProductionConfig}


def get_config(name=None):
    name = (name or os.environ.get("FLASK_CONFIG") or "development").strip().lower()
    if name not in CONFIGS:
        raise RuntimeError(f"Unknown FLASK_CONFIG {name!r}. Use one of: {', '.join(CONFIGS)}")
    return CONFIGS[name]()


def check_production(config):
    """Refuse to start an unsafe production server instead of running with weak settings."""
    if len(config.SECRET_KEY) < 32:
        raise RuntimeError("Production needs SECRET_KEY: at least 32 random characters "
                           "(python -c \"import secrets; print(secrets.token_hex(32))\").")
    if not config.SQLALCHEMY_DATABASE_URI:
        raise RuntimeError("Production needs DATABASE_URL (your PostgreSQL connection string).")
    if config.SQLALCHEMY_DATABASE_URI.startswith("sqlite"):
        raise RuntimeError("Production must use PostgreSQL: the disk on free hosting is wiped on restart.")
