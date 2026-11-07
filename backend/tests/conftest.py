"""Keep importing app.py from creating the development database during tests."""

import os
import tempfile

os.environ.setdefault(
    "TT_DATABASE", os.path.join(tempfile.gettempdir(), "thomas-transfer-import.db")
)
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("TT_ADMIN_PASSWORD", "admin-test-pass")
