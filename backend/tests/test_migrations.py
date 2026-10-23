"""The migration files must build exactly the tables the models describe, and must be reversible."""
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from flask_migrate import downgrade, upgrade
from sqlalchemy import inspect

from backend.app.extensions import db

TABLES = {"users", "experiments", "metrics", "results", "chat_sessions", "chat_messages",
          "activity_events", "people", "token_blocklist"}


def test_migrations_match_models(app):
    # conftest already ran `upgrade`; nothing may be left for a new migration to do.
    with db.engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), db.metadata)
    assert diff == [], f"models changed without a migration: {diff}  ->  run `flask db migrate`"
    assert TABLES <= set(inspect(db.engine).get_table_names())


def test_downgrade_and_upgrade_again(app):
    downgrade(revision="base")
    assert set(inspect(db.engine).get_table_names()) == {"alembic_version"}
    upgrade()
    assert TABLES <= set(inspect(db.engine).get_table_names())
