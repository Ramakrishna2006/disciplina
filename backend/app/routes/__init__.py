"""API blueprints. Each later stage adds its own (auth, chat, experiments, ...) to this list."""
from . import system

BLUEPRINTS = [system.bp]
