"""API blueprints. Each later stage adds its own (chat, experiments, ...) to this list."""
from . import auth, system, users

BLUEPRINTS = [system.bp, auth.bp, users.bp]
