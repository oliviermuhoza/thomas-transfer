import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import backend.app as backend_app  # noqa: E402
from backend.app import create_app  # noqa: E402
from backend.db import get_db, init_db  # noqa: E402

ADMIN_EMAIL = "tomsafaris@gmail.com"
ADMIN_PASSWORD = "admin-test-pass"


@pytest.fixture()
def app(tmp_path):
    return create_app(
        database=str(tmp_path / "test.db"),
        secret_key="test-secret",
        admin_password=ADMIN_PASSWORD,
        admin_email=ADMIN_EMAIL,
    )


@pytest.fixture()
def client(app):
    return app.test_client()


def future(minutes=60):
    moment = datetime.now() + timedelta(minutes=minutes)
    return moment.replace(second=0, microsecond=0).isoformat(timespec="minutes")


def csrf_headers(client):
    token = client.get("/api/csrf").get_json()["csrf_token"]
    return {"X-CSRF-Token": token}


def api_post(client, url, json=None):
    return client.post(url, json=json or {}, headers=csrf_headers(client))


def register(client, email="jane@example.com", password="secret123"):
    return api_post(
        client,
        "/api/register",
        json={
            "first_name": "Jane",
            "last_name": "Doe",
            "email": email,
            "phone": "+250700000000",
            "password": password,
        },
    )


def login(client, email=ADMIN_EMAIL, password=ADMIN_PASSWORD):
    return api_post(client, "/api/login", json={"email": email, "password": password})


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


def test_site_is_served(client):
    page = client.get("/")
    assert page.status_code == 200
    assert b"Thomas Transfer" in page.data

    assert client.get("/css/styles.css").status_code == 200
    assert client.get("/js/dashboard.js").status_code == 200
    assert client.get("/assets/images/logo.png").status_code == 200
    assert client.get("/app.py").status_code == 404
    assert client.get("/data/thomas.db").status_code == 404


def test_me_is_null_without_session(client):
    response = client.get("/api/me")
    assert response.status_code == 200
    data = response.get_json()
    assert data["user"] is None
    assert data["csrf_token"]


def test_register_login_logout(client):
    response = register(client)
    assert response.status_code == 201
    user = response.get_json()["user"]
    assert user["name"] == "Jane Doe"
    assert user["admin"] is False
    assert "password" not in user

    assert client.get("/api/me").get_json()["user"]["email"] == "jane@example.com"

    assert register(client).status_code == 409
    assert register(client, email="short@example.com", password="123").status_code == 400
    assert register(client, email="not-an-email").status_code == 400

    assert api_post(client, "/api/logout", json={}).status_code == 200
    assert client.get("/api/me").get_json()["user"] is None

    assert login(client, "jane@example.com", "wrong-password").status_code == 401
    assert login(client, "jane@example.com", "secret123").status_code == 200
    assert client.get("/api/me").get_json()["user"]["email"] == "jane@example.com"


def test_fleet_is_seeded(client):
    cars = client.get("/api/cars").get_json()
    assert len(cars) == 8
    assert cars[0]["name"] == "Toyota Corolla Hybrid"
    assert cars[0]["status"] == "available"
    assert cars[0]["image"].startswith("/assets/images/cars/")
    for car in cars:
        assert {"specs", "price", "week"} <= set(car)
    assert "5 seats" in cars[0]["specs"][0]
    assert cars[0]["price"] == "45,000 RWF"
    assert cars[0]["week"].startswith("31,500 RWF/day")
    assert len(client.get("/api/cars?available=1").get_json()) == 8


def test_permissions(client):
    assert client.get("/api/bookings").status_code == 401
    assert client.get("/api/report").status_code == 401
    assert api_post(client, "/api/bookings", json=booking_payload()).status_code == 401

    register(client)
    assert client.get("/api/report").status_code == 403
    assert api_post(client, "/api/cars/1/status", json={"status": "maintenance"}).status_code == 403


def test_booking_flow(client):
    register(client)
    response = api_post(client, "/api/bookings", json=booking_payload())
    assert response.status_code == 201
    booking_id = response.get_json()["id"]

    available = client.get("/api/cars?available=1").get_json()
    assert len(available) == 7
    assert all(car["id"] != 1 for car in available)

    bookings = client.get("/api/bookings").get_json()
    assert len(bookings) == 1
    assert bookings[0]["status"] == "pending"
    assert bookings[0]["car_name"] == "Toyota Corolla Hybrid"
    assert bookings[0]["pickup"] == "Kigali International Airport"
    assert "T" in bookings[0]["trip_at"]

    # Customers cannot confirm their own booking.
    assert (
        api_post(
            client, f"/api/bookings/{booking_id}/status", json={"status": "confirmed"}
        ).status_code
        == 400
    )

    admin = client.application.test_client()
    assert login(admin).status_code == 200
    assert admin.get("/api/bookings").get_json()[0]["customer"] == "Jane Doe"
    assert (
        api_post(
            admin, f"/api/bookings/{booking_id}/status", json={"status": "confirmed"}
        ).status_code
        == 200
    )
    assert (
        api_post(
            admin, f"/api/bookings/{booking_id}/status", json={"status": "completed"}
        ).status_code
        == 200
    )

    # Completed bookings release the car again.
    assert len(admin.get("/api/cars?available=1").get_json()) == 8

    report = admin.get("/api/report").get_json()
    assert report["cars"]["total"] == 8
    assert report["cars"]["available"] == 8
    assert report["bookings"]["total"] == 1
    assert report["bookings"]["completed"] == 1
    assert report["per_car"][0]["total"] == 1
    assert report["per_car"][0]["completed"] == 1


def test_confirming_booking_sends_confirmation_email(client, monkeypatch):
    sent = []

    def fake_send(to, subject, body):
        sent.append({"to": to, "subject": subject, "body": body})

    monkeypatch.setattr(backend_app, "mail_configured", lambda: True)
    monkeypatch.setattr(backend_app, "send_email", fake_send)

    register(client)
    booking_id = api_post(client, "/api/bookings", json=booking_payload()).get_json()["id"]
    assert sent == []

    admin = client.application.test_client()
    assert login(admin).status_code == 200
    assert (
        api_post(
            admin, f"/api/bookings/{booking_id}/status", json={"status": "confirmed"}
        ).status_code
        == 200
    )

    assert len(sent) == 1
    assert sent[0]["to"] == "jane@example.com"
    assert "confirmed" in sent[0]["subject"]
    assert "Kigali International Airport" in sent[0]["body"]
    assert "Toyota Corolla Hybrid" in sent[0]["body"]

    # Cancelling afterwards sends no further email.
    assert (
        api_post(
            admin, f"/api/bookings/{booking_id}/status", json={"status": "cancelled"}
        ).status_code
        == 200
    )
    assert len(sent) == 1


def test_customer_can_cancel_and_car_is_released(client):
    register(client)
    booking_id = api_post(client, "/api/bookings", json=booking_payload()).get_json()["id"]
    assert (
        api_post(
            client, f"/api/bookings/{booking_id}/status", json={"status": "cancelled"}
        ).status_code
        == 200
    )
    assert len(client.get("/api/cars?available=1").get_json()) == 8
    assert client.get("/api/bookings").get_json()[0]["status"] == "cancelled"


def test_booking_validation(client):
    register(client)

    assert api_post(client, "/api/bookings", json={}).status_code == 400
    assert (
        api_post(
            client,
            "/api/bookings",
            json=booking_payload(trip_at="2020-01-01T10:00"),
        ).status_code
        == 400
    )
    assert (
        api_post(client, "/api/bookings", json=booking_payload(passengers=0)).status_code
        == 400
    )
    assert (
        api_post(client, "/api/bookings", json=booking_payload(passengers=61)).status_code
        == 400
    )
    assert (
        api_post(client, "/api/bookings", json=booking_payload(car_id=999)).status_code == 404
    )


def test_maintenance_blocks_booking_and_car_status_management(client):
    admin = client.application.test_client()
    login(admin)

    assert (
        api_post(admin, "/api/cars/2/status", json={"status": "maintenance"}).status_code
        == 200
    )
    assert admin.get("/api/cars?available=1").get_json()[0]["id"] != 2

    customer = client.application.test_client()
    register(customer)
    assert api_post(customer, "/api/bookings", json=booking_payload(car_id=2)).status_code == 409

    # A booked car cannot be switched to maintenance/available by hand.
    assert api_post(customer, "/api/bookings", json=booking_payload(car_id=3)).status_code == 201
    assert (
        api_post(admin, "/api/cars/3/status", json={"status": "maintenance"}).status_code
        == 409
    )

    assert (
        api_post(admin, "/api/cars/2/status", json={"status": "available"}).status_code == 200
    )
    assert len(admin.get("/api/cars?available=1").get_json()) == 7


def test_comments_contact_and_report(client):
    assert (
        api_post(
            client,
            "/api/comment",
            json={"name": "Aline", "rating": "5 - Excellent", "text": "Great trip."},
        ).status_code
        == 201
    )
    assert (
        api_post(
            client,
            "/api/comment",
            json={"name": "Aline", "rating": "nope", "text": "Hi"},
        ).status_code
        == 400
    )

    assert (
        api_post(
            client,
            "/api/contact",
            json={
                "name": "Aline",
                "email": "aline@example.com",
                "phone": "+250700000001",
                "service": "Support message",
                "message": "Please call me.",
            },
        ).status_code
        == 201
    )
    assert (
        api_post(
            client,
            "/api/contact",
            json={"name": "Aline", "email": "bad", "message": "Hi"},
        ).status_code
        == 400
    )

    admin = client.application.test_client()
    login(admin)
    report = admin.get("/api/report").get_json()
    assert report["comments"]["count"] == 1
    assert report["comments"]["average"] == 5.0
    assert report["messages"] == 1
    assert report["accounts"] == 1  # only the seeded admin exists in this test


def test_unwritable_database_falls_back(monkeypatch, tmp_path):
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setattr(backend_app, "PACKAGE_DIR", tmp_path / "project")

    app = create_app(
        database=str(blocker / "thomas.db"),
        secret_key="test-secret",
        admin_password=ADMIN_PASSWORD,
    )
    assert app.config["DATABASE"] != str(blocker / "thomas.db")
    assert app.test_client().get("/api/me").status_code == 200


def test_vercel_production_refuses_ephemeral_database(monkeypatch, tmp_path):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("TT_ENV", "production")
    monkeypatch.delenv("TT_ALLOW_EPHEMERAL_DB", raising=False)
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="persistent database"):
        create_app(database=str(tmp_path / "vercel.db"), production=True)


def test_allow_ephemeral_flag_boots_without_secret(monkeypatch, tmp_path):
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("TT_ENV", "production")
    monkeypatch.setenv("TT_ALLOW_EPHEMERAL_DB", "1")
    monkeypatch.delenv("TURSO_DATABASE_URL", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("TT_COOKIE_SECURE", raising=False)
    monkeypatch.delenv("TT_ADMIN_PASSWORD", raising=False)

    app = create_app(database=str(tmp_path / "vercel.db"), production=True)

    assert app.config["PRODUCTION"] is True
    assert app.config["SESSION_COOKIE_SECURE"] is True
    assert app.config["SECRET_KEY"]
    assert app.test_client().get("/api/me").status_code == 200


def test_auto_init_can_be_disabled(tmp_path):
    app = create_app(
        database=str(tmp_path / "manual.db"),
        secret_key="test-secret",
        admin_password=ADMIN_PASSWORD,
        admin_email=ADMIN_EMAIL,
        auto_init=False,
    )
    with app.app_context():
        tables = {
            row["name"]
            for row in get_db().execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert "users" not in tables

        init_db(ADMIN_PASSWORD, admin_email=ADMIN_EMAIL)
        assert get_db().execute("SELECT COUNT(*) FROM cars").fetchone()[0] == 8
        assert get_db().execute("SELECT COUNT(*) FROM fares").fetchone()[0] >= 5


def test_live_deployment_requires_an_initialised_database(monkeypatch, tmp_path):
    monkeypatch.setenv("TT_COOKIE_SECURE", "1")
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.setattr(backend_app, "_is_ephemeral_db", lambda database: False)

    with pytest.raises(RuntimeError, match="no schema"):
        create_app(
            database=str(tmp_path / "empty.db"),
            secret_key="test-secret",
            admin_password=ADMIN_PASSWORD,
            production=True,
        )


def test_production_requires_secure_cookie(monkeypatch, tmp_path):
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("TT_COOKIE_SECURE", raising=False)

    with pytest.raises(RuntimeError, match="TT_COOKIE_SECURE"):
        create_app(
            database=str(tmp_path / "prod.db"),
            secret_key="test-secret",
            admin_password=ADMIN_PASSWORD,
            production=True,
        )
