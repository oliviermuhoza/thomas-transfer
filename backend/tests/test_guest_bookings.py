"""Public reservations must land in bookings, never in messages."""

import sqlite3
from datetime import datetime, timedelta

import pytest

from backend.app import create_app
from backend.db import get_db

ADMIN_EMAIL = "admin@example.com"
ADMIN_PASSWORD = "admin-test-pass"


@pytest.fixture()
def app(tmp_path):
    return create_app(
        database=str(tmp_path / "guest.db"),
        secret_key="test-secret",
        admin_password=ADMIN_PASSWORD,
        admin_email=ADMIN_EMAIL,
    )


@pytest.fixture()
def client(app):
    return app.test_client()


def csrf_headers(client):
    return {"X-CSRF-Token": client.get("/api/csrf").get_json()["csrf_token"]}


def api_post(client, url, payload=None):
    return client.post(url, json=payload or {}, headers=csrf_headers(client))


def future(minutes=60):
    moment = datetime.now() + timedelta(minutes=minutes)
    return moment.replace(second=0, microsecond=0).isoformat(timespec="minutes")


def guest_car_payload(**overrides):
    payload = {
        "kind": "car",
        "car_id": 1,
        "name": "Aline Guest",
        "email": "aline@example.com",
        "phone": "+250788111222",
        "pickup": "Kigali International Airport",
        "trip_at": future(),
        "passengers": 2,
        "notes": "Two bags",
    }
    payload.update(overrides)
    return payload


def guest_tour_payload(**overrides):
    payload = {
        "kind": "tour",
        "tour_name": "Akagera safari",
        "name": "Eric Guest",
        "email": "eric@example.com",
        "phone": "+250788333444",
        "pickup": "Kigali hotel",
        "trip_at": future(minutes=60 * 24),
        "passengers": 3,
        "notes": "",
    }
    payload.update(overrides)
    return payload


def counts(app):
    with app.app_context():
        db = get_db()
        return {
            "bookings": db.execute("SELECT COUNT(*) FROM bookings").fetchone()[0],
            "messages": db.execute("SELECT COUNT(*) FROM messages").fetchone()[0],
        }


def test_guest_car_reservation_is_a_booking(app, client):
    response = api_post(client, "/api/bookings/guest", guest_car_payload())
    assert response.status_code == 201, response.get_json()
    booking_id = response.get_json()["id"]

    with app.app_context():
        row = get_db().execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
        car = get_db().execute("SELECT status FROM cars WHERE id = 1").fetchone()

    assert row["kind"] == "car"
    assert row["user_id"] is None
    assert row["car_id"] == 1
    assert row["customer_name"] == "Aline Guest"
    assert row["customer_email"] == "aline@example.com"
    assert row["customer_phone"] == "+250788111222"
    assert row["status"] == "pending"
    assert car["status"] == "booked"
    assert counts(app) == {"bookings": 1, "messages": 0}


def test_guest_tour_request_is_a_booking(app, client):
    response = api_post(client, "/api/bookings/guest", guest_tour_payload())
    assert response.status_code == 201, response.get_json()

    with app.app_context():
        row = get_db().execute("SELECT * FROM bookings").fetchone()

    assert row["kind"] == "tour"
    assert row["car_id"] is None
    assert row["user_id"] is None
    assert row["tour_name"] == "Akagera safari"
    assert counts(app) == {"bookings": 1, "messages": 0}


def test_contact_and_support_stay_in_messages(app, client):
    response = api_post(
        client,
        "/api/contact",
        {
            "name": "Aline",
            "email": "aline@example.com",
            "phone": "+250788111222",
            "service": "Airport transfer",
            "message": "Do you have a van?",
        },
    )
    assert response.status_code == 201
    assert counts(app) == {"bookings": 0, "messages": 1}


def test_guest_booking_validation(client):
    assert api_post(
        client, "/api/bookings/guest", guest_car_payload(car_id=None)
    ).status_code == 400
    assert api_post(
        client, "/api/bookings/guest", guest_car_payload(email="not-an-email")
    ).status_code == 400
    assert api_post(
        client, "/api/bookings/guest", guest_tour_payload(tour_name="")
    ).status_code == 400

    assert api_post(client, "/api/bookings/guest", guest_car_payload()).status_code == 201
    assert api_post(client, "/api/bookings/guest", guest_car_payload()).status_code == 409


def test_admin_sees_guest_and_tour_bookings(client):
    api_post(client, "/api/bookings/guest", guest_car_payload())
    api_post(client, "/api/bookings/guest", guest_tour_payload())

    admin = client.application.test_client()
    assert api_post(
        admin, "/api/login", {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    ).status_code == 200

    rows = admin.get("/api/bookings").get_json()
    assert len(rows) == 2
    by_kind = {row["kind"]: row for row in rows}
    assert by_kind["car"]["customer"] == "Aline Guest"
    assert by_kind["car"]["phone"] == "+250788111222"
    assert by_kind["car"]["car_name"] == "Toyota Corolla Hybrid"
    assert by_kind["tour"]["car_name"] == "Akagera safari"


OLD_BOOKINGS = """
CREATE TABLE bookings (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  car_id     INTEGER NOT NULL REFERENCES cars(id),
  pickup     TEXT    NOT NULL,
  dropoff    TEXT    NOT NULL,
  trip_at    TEXT    NOT NULL,
  passengers INTEGER NOT NULL,
  notes      TEXT    NOT NULL DEFAULT '',
  status     TEXT    NOT NULL DEFAULT 'pending',
  paid_amount REAL   NOT NULL DEFAULT 0,
  paid_method TEXT   NOT NULL DEFAULT '',
  paid_at     TEXT   NOT NULL DEFAULT '',
  created_at TEXT    NOT NULL DEFAULT (datetime('now'))
)
"""


def test_old_bookings_table_is_rebuilt_without_losing_rows(tmp_path):
    database = str(tmp_path / "old.db")
    create_app(
        database=database,
        secret_key="test-secret",
        admin_password=ADMIN_PASSWORD,
        admin_email=ADMIN_EMAIL,
    )

    with sqlite3.connect(database) as con:
        con.execute("DROP TABLE bookings")
        con.execute(OLD_BOOKINGS)
        con.execute(
            "INSERT INTO bookings (user_id, car_id, pickup, dropoff, trip_at,"
            " passengers, notes, status)"
            " VALUES (1, 1, 'Airport', 'Hotel', '2026-12-01T10:00', 2, 'old', 'pending')"
        )
        con.commit()

    app = create_app(
        database=database,
        secret_key="test-secret",
        admin_password=ADMIN_PASSWORD,
        admin_email=ADMIN_EMAIL,
    )
    with app.app_context():
        db = get_db()
        columns = {row["name"] for row in db.execute("PRAGMA table_info(bookings)")}
        row = db.execute("SELECT * FROM bookings").fetchone()
        db.execute(
            "INSERT INTO bookings (car_id, kind, customer_name, pickup, trip_at, passengers)"
            " VALUES (NULL, 'tour', 'Guest', 'Hotel', '2026-12-02T10:00', 2)"
        )
        guest = db.execute("SELECT * FROM bookings WHERE customer_name = 'Guest'").fetchone()

    assert {"kind", "customer_name", "customer_email", "customer_phone"} <= columns
    assert row["pickup"] == "Airport" and row["user_id"] == 1 and row["kind"] == "car"
    assert guest["user_id"] is None and guest["car_id"] is None
