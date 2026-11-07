"""Vercel entrypoint for the Flask app.

Vercel's Flask preset looks for a Flask instance named ``app`` at supported
entrypoints (``app.py`` at the repository root). Keeping this file at the root
makes Vercel bundle the whole project (templates and ``web/`` assets included).
"""

from backend.app import app

__all__ = ["app"]
