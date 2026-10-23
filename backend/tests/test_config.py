"""Settings: production refuses unsafe settings, and database URLs are normalised."""
import pytest

from backend import config


def test_postgres_url_uses_psycopg(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@host/db")
    assert config.database_url("") == "postgresql+psycopg://u:p@host/db"
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@host/db?sslmode=require")
    assert config.database_url("") == "postgresql+psycopg://u:p@host/db?sslmode=require"


def test_default_database_when_unset(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert config.database_url("sqlite:///x.db") == "sqlite:///x.db"


def test_unknown_profile():
    with pytest.raises(RuntimeError, match="Unknown FLASK_CONFIG"):
        config.get_config("staging")


class Prod:
    SECRET_KEY = "k" * 64
    JWT_SECRET_KEY = "j" * 64
    SQLALCHEMY_DATABASE_URI = "postgresql+psycopg://u:p@host/db"


@pytest.mark.parametrize("change, message", [
    ({"SECRET_KEY": "short"}, "SECRET_KEY"),
    ({"SECRET_KEY": ""}, "SECRET_KEY"),
    ({"JWT_SECRET_KEY": "short"}, "JWT_SECRET_KEY"),
    ({"JWT_SECRET_KEY": "k" * 64}, "must be different"),
    ({"SQLALCHEMY_DATABASE_URI": ""}, "DATABASE_URL"),
    ({"SQLALCHEMY_DATABASE_URI": "sqlite:///x.db"}, "PostgreSQL"),
])
def test_production_refuses_unsafe_settings(change, message):
    cfg = type("Bad", (Prod,), change)()
    with pytest.raises(RuntimeError, match=message):
        config.check_production(cfg)


def test_production_accepts_safe_settings():
    config.check_production(Prod())


def test_testing_profile_never_uses_instance_folder():
    cfg = config.get_config("testing")
    assert cfg.SQLALCHEMY_DATABASE_URI == "sqlite://" and cfg.SECRET_KEY


def test_production_cookies_are_https_only():
    assert config.ProductionConfig.JWT_COOKIE_SECURE is True and config.ProductionConfig.TRUST_PROXY is True
    assert config.DevelopmentConfig.JWT_COOKIE_SECURE is False
