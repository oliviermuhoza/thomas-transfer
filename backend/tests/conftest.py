"""Keep importing app.py from creating the development database during tests."""

import os
import tempfile

# Tests must not read a developer's local .env: its TT_ADMIN_EMAIL may differ
# from the admin these tests create and log in as.
os.environ["TT_NO_ENV_FILE"] = "1"
# Never let an exported Turso database (or the ephemeral override) turn the
# suite into a production client.
os.environ.pop("TURSO_DATABASE_URL", None)
os.environ.pop("TURSO_AUTH_TOKEN", None)
os.environ.pop("TT_ALLOW_EPHEMERAL_DB", None)
os.environ.setdefault(
    "TT_DATABASE", os.path.join(tempfile.gettempdir(), "thomas-transfer-import.db")
)
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("TT_ADMIN_PASSWORD", "admin-test-pass")
