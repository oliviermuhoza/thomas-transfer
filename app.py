"""Vercel entrypoint for the Flask app.

Vercel's Flask framework preset looks for a top-level ``app`` at supported
entrypoints (``app.py``, ``index.py``, ``main.py``, ``wsgi.py``, ...). Keeping
this file at the repository root makes Vercel bundle the whole project (templates
and ``web/`` assets included) instead of treating ``api/index.py`` as a standalone
function that cannot import ``backend``.
"""

from backend.app import app

__all__ = ["app"]
