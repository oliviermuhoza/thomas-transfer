"""Vercel serverless entrypoint: exposes the Flask app to Vercel.

All routes (pages, static assets, API) are served by the backend Flask app;
vercel.json rewrites every request to this function.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app import app
