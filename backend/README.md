# Disciplina Studio: backend

Flask API for the Disciplina Studio web app. It uses the engine in [`../llm/`](../llm) and stores
accounts, experiments and chats in a database (SQLite on your laptop, PostgreSQL online).

Run every command **from the repository folder** (the one with `main.py`), with the virtual environment active.

```powershell
pip install -r backend/requirements-dev.in      # once
flask --app backend.app db upgrade              # create / update the database tables
flask --app backend.app seed                    # add the 40 people and the reference experiment
flask --app backend.app run                     # http://127.0.0.1:5000/api/health
pytest                                          # backend tests
```

| Path | What it is |
| --- | --- |
| `config.py` | Settings for development, testing and production; reads `backend/.env` |
| `app/__init__.py` | `create_app()`, the application factory: builds and wires the app |
| `app/extensions.py` | The shared `db` (SQLAlchemy) and `migrate` (Alembic) objects |
| `app/models/` | The nine database tables |
| `app/routes/` | API endpoints, one blueprint per area (`system.py`: `/api/health`) |
| `app/utils/` | JSON responses and errors, security headers, request logging |
| `app/cli.py` | `flask seed` (more commands in later stages) |
| `migrations/` | One file per database change, created by `flask db migrate` |
| `tests/` | pytest tests; each test gets its own temporary database |
| `instance/` | Your local database and secret key. **Git-ignored, never commit it** |
| `wsgi.py` | Entry point for gunicorn in production |

**Changing a table:** edit the model, then `flask --app backend.app db migrate -m "what changed"`,
read the new file in `migrations/versions/`, and apply it with `db upgrade`. The test
`test_migrations_match_models` fails if a model changes without a migration.

**Your data is safe:** `db upgrade` only applies new migrations and `seed` only adds missing rows.
Nothing in the setup deletes data. Backup: stop the server and copy `backend/instance/disciplina.db`.
