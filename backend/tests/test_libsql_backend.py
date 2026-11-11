"""The libSQL/Turso driver must behave like sqlite3 for the whole app.

These run the real routes against a local ``file:`` database through the
adapter in ``backend/dbdriver.py``. They exercise the differences that broke
the first attempt: tuple rows, no ``row_factory``, non-iterable cursors and
``ValueError`` on constraint violations.
"""

import sqlite3
from datetime import datetime, timedelta

import pytest

from backend.app import create_app
from backend.db import get_db

ADMIN_EMAIL = "admin@thomastransfer.com"
ADMIN_PASSWORD = "admin-test-pass"


@pytest.fixture()
def app(tmp_path):
    return create_app(
        database=str(tmp_path / "libsql.db"),
        secret_key="test-secret",
        admin_password=ADMIN_PASSWORD,
        admin_email=ADMIN_EMAIL,
        db_driver="libsql",
    )


@pytest.fixture()
def client(app):
    return app.test_client()


def csrf_headers(client):
    return {"X-CSRF-Token": client.get("/api/csrf").get_json()["csrf_token"]}


def api_post(client, url, json=None):
    return client.post(url, json=json or {}, headers=csrf_headers(client))


def login(client, email=ADMIN_EMAIL, password=ADMIN_PASSWORD):
    return api_post(client, "/api/login", {"email": email, "password": password})


def register(client, email="jane@example.com"):
    return api_post(
        client,
        "/api/register",
        {
            "first_name": "Jane",
            "last_name": "Doe",
            "email": email,
            "phone": "+250700000000",
            "password": "secret123",
        },
    )


def future(minutes=60):
    moment = datetime.now() + timedelta(minutes=minutes)
    return moment.replace(second=0, microsecond=0).isoformat(timespec="minutes")


def booking_payload(**overrides):
    payload = {
        "car_id": 1,
        "pickup": "Kigali International Airport",
        "dropoff": "Kigali Marriott Hotel",
        "trip_at": future(),
        "passengers": 2,
        "notes": "",
    }
    payload.update(overrides)
    return payload


def test_schema_rows_and_seed(app, client):
    assert app.config["DB_DRIVER"] == "libsql"

    cars = client.get("/api/cars").get_json()
    assert len(cars) == 8
    assert cars[0]["name"] == "Toyota Corolla Hybrid"
    assert isinstance(cars[0]["specs"], list)

    fares = client.get("/pay")
    assert fares.status_code == 200
    with app.app_context():
        fare_count = get_db().execute("SELECT COUNT(*) AS n FROM fares").fetchone()["n"]
    assert fare_count >= 5

    assert login(client).status_code == 200
    me = client.get("/api/me").get_json()
    assert me["user"]["email"] == ADMIN_EMAIL
    assert me["user"]["admin"] is True


def test_booking_flow(client):
    assert register(client).status_code == 201

    created = api_post(client, "/api/bookings", booking_payload())
    assert created.status_code == 201
    booking_id = created.get_json()["id"]

    bookings = client.get("/api/bookings").get_json()
    assert len(bookings) == 1
    assert bookings[0]["status"] == "pending"
    assert bookings[0]["car_name"] == "Toyota Corolla Hybrid"

    admin = client.application.test_client()
    assert login(admin).status_code == 200
    confirmed = api_post(
        admin, f"/api/bookings/{booking_id}/status", {"status": "confirmed"}
    )
    assert confirmed.status_code == 200
    assert confirmed.get_json()["status"] == "confirmed"

    report = admin.get("/api/report").get_json()
    assert report["bookings"]["confirmed"] == 1
    assert report["cars"]["total"] == 8


def test_registered_user_can_log_in_from_a_new_session(client):
    """Registration stores a hash that a later, cookie-less login accepts.

    The seeded admin is hashed at boot in the same process, so it never proves
    that a hash written through the libSQL driver reads back and verifies.
    """
    assert register(client).status_code == 201

    returning = client.application.test_client()
    assert login(returning, email="jane@example.com", password="secret123").status_code == 200

    me = returning.get("/api/me").get_json()
    assert me["user"]["email"] == "jane@example.com"
    assert me["user"]["admin"] is False


def test_migrations_and_aggregates(app, client):
    with app.app_context():
        db = get_db()
        columns = {row["name"] for row in db.execute("PRAGMA table_info(cars)")}
        assert {"capacity", "price", "week", "specs"} <= columns

        db.execute(
            "INSERT INTO messages (name, email, message) VALUES (?, ?, ?)",
            ("Old", "old@example.com", "Hello"),
        )
        db.commit()

    admin = client.application.test_client()
    assert login(admin).status_code == 200
    messages = admin.get("/api/admin/messages").get_json()
    assert messages[0]["name"] == "Old"
    assert messages[0]["handled"] is False


def test_constraint_violation_is_sqlite_integrity_error(app):
    with app.app_context():
        db = get_db()
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO users (first_name, last_name, email, phone, password_hash)"
                " VALUES (?, ?, ?, ?, ?)",
                ("A", "B", ADMIN_EMAIL, "+250700000001", "x"),
            )
