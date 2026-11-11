"""Read-only report on the Turso/libSQL database the app is configured to use.

Usage (from the repo root, with TT_DB_DRIVER unset):
    .\\.venv\\Scripts\\python.exe backend\\tools\\turso_report.py [email]

Reads TURSO_DATABASE_URL and TURSO_AUTH_TOKEN from the environment or .env.
Never prints password hashes, only their method prefix and length.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def load_env(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def main():
    load_env(os.path.join(ROOT, ".env"))
    url = os.environ.get("TURSO_DATABASE_URL", "").strip()
    token = os.environ.get("TURSO_AUTH_TOKEN", "").strip()
    if not url:
        print("TURSO_DATABASE_URL is not set. Add it to .env or the environment.")
        return 1
    if not token:
        print("TURSO_AUTH_TOKEN is not set, but TURSO_DATABASE_URL is.")
        return 1

    from backend.dbdriver import connect

    db = connect(url, driver="libsql", auth_token=token)
    probe = sys.argv[1] if len(sys.argv) > 1 else None

    def scalar(sql, params=()):
        row = db.execute(sql, params).fetchone()
        return None if row is None else row[0]

    print(f"target: {url.split('?')[0]}")
    for table in ("users", "cars", "bookings", "fares", "messages"):
        try:
            print(f"{table:10} rows={scalar(f'SELECT COUNT(*) FROM {table}')}")
        except Exception as exc:  # noqa: BLE001
            print(f"{table:10} unavailable: {exc}")

    print("\nusers:")
    rows = db.execute(
        "SELECT id, email, is_admin, active, password_hash, created_at"
        " FROM users ORDER BY id"
    ).fetchall()
    for row in rows:
        hashed = row["password_hash"] or ""
        method = hashed.split("$", 1)[0] or "(empty)"
        print(
            f"  id={row['id']:<3} admin={row['is_admin']} active={row['active']}"
            f" hash={method} len={len(hashed)} created={row['created_at']} {row['email']}"
        )
    if not rows:
        print("  (none)")

    admins = sum(1 for row in rows if row["is_admin"])
    print(f"\nadmins: {admins}")

    if probe:
        found = [row for row in rows if row["email"].lower() == probe.lower()]
        print(f"\nlookup {probe!r}: {'found' if found else 'MISSING'}")
        for row in found:
            print(f"  active={row['active']} created={row['created_at']}")

    db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
