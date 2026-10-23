"""Entry point for the production server:  gunicorn backend.wsgi:app"""
from backend.app import create_app

app = create_app()
