"""Create, migrate and seed the configured database once.

Live deployments no longer run schema/seed work at startup, so run this after
provisioning a database or changing ``schema.sql``:

    python -m backend.initdb

It uses the same environment as the app (``TURSO_*`` or ``TT_DATABASE``,
``TT_ADMIN_*``), so run it locally with the production values in ``.env``.
"""

import os
import sys

try:
    from .app import create_app
    from .db import get_db, init_db
except ImportError:  # executed as a plain script from the repository root
    from backend.app import create_app
    from backend.db import get_db, init_db


def main():
    app = create_app(auto_init=False)
    with app.app_context():
        init_db(
            os.environ.get("TT_ADMIN_PASSWORD"),
            production=app.config["PRODUCTION"],
            ephemeral=app.config["EPHEMERAL_DB"],
        )
        db = get_db()
        counts = {
            table: db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("users", "cars", "fares", "bookings")
        }
    target = app.config["DATABASE"]
    print(f"Initialised {target}")
    print(
        "users={users} cars={cars} fares={fares} bookings={bookings}".format(**counts)
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
