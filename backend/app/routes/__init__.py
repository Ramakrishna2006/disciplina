"""API blueprints. Each later stage adds its own (chat, experiments, ...) to this list.
`frontend` goes last: it answers every address the API does not."""
from . import auth, dashboard, experiments, frontend, people, playground, system, users

BLUEPRINTS = [system.bp, auth.bp, users.bp, playground.bp, people.bp, experiments.bp, dashboard.bp, frontend.bp]
