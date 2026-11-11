"""Keep importing app.py from creating the development database during tests."""

import os
import tempfile

# Tests must not read a developer's local .env: its TT_ADMIN_EMAIL may differ
# from the admin these tests create and log in as.
os.environ["TT_NO_ENV_FILE"] = "1"
os.environ.setdefault(
    "TT_DATABASE", os.path.join(tempfile.gettempdir(), "thomas-transfer-import.db")
)
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("TT_ADMIN_PASSWORD", "admin-test-pass")
