"""Vercel entrypoint for the Flask app.

Vercel's Flask preset looks for a Flask instance named ``app`` at supported
entrypoints (``app.py`` at the repository root). Keeping this file at the root
makes Vercel bundle the whole project (templates and ``web/`` assets included).

The import guard is TEMPORARY: it surfaces startup errors while diagnosing the
production 500 so they are visible without Vercel runtime logs. Remove it once
the deployment is healthy.
"""

import traceback

try:
    from backend.app import app
except BaseException:  # pragma: no cover - diagnostic path only
    _startup_error = traceback.format_exc()
    traceback.print_exc()

    from flask import Flask, Response

    app = Flask(__name__)

    @app.get("/", defaults={"path": ""})
    @app.get("/<path:path>")
    def _startup_diagnostic(path):
        return Response(_startup_error, status=500, mimetype="text/plain")


__all__ = ["app"]
