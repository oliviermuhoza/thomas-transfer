"""Admin records API and /admin page guards."""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app import create_app  # noqa: E402

ADMIN_EMAIL = "admin@thomastransfer.com"
ADMIN_PASSWORD = "admin-test-pass"


@pytest.fixture()
def client(tmp_path):
    app = create_app(
        database=str(tmp_path / "admin.db"),
        secret_key="test-secret",
        admin_password=ADMIN_PASSWORD,
    )
    return app.test_client()


def csrf_headers(client):
    return {"X-CSRF-Token": client.get("/api/csrf").get_json()["csrf_token"]}


def api_post(client, url, json=None):
    return client.post(url, json=json or {}, headers=csrf_headers(client))


def api_delete(client, url):
    headers = csrf_headers(client)
    headers["Content-Type"] = "application/json"
    return client.delete(url, headers=headers)


def api_patch(client, url, json=None):
    return client.patch(url, json=json or {}, headers=csrf_headers(client))


def login_admin(client):
    return api_post(
        client,
        "/api/login",
        {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
    )


def register_customer(client, email="jane@example.com"):
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


READ_ENDPOINTS = [
    "/api/admin/users",
    "/api/admin/messages",
    "/api/admin/comments",
    "/api/admin/fares",
    "/api/admin/export/bookings.csv",
    "/api/admin/export/messages.csv",
]


@pytest.mark.parametrize("url", READ_ENDPOINTS)
def test_admin_endpoints_require_login(client, url):
    assert client.get(url).status_code == 401


@pytest.mark.parametrize("url", READ_ENDPOINTS)
def test_admin_endpoints_reject_customers(client, url):
    assert register_customer(client).status_code == 201
    assert client.get(url).status_code == 403


def test_admin_users_lists_accounts_without_hashes(client):
    assert register_customer(client).status_code == 201
    assert login_admin(client).status_code == 200

    response = client.get("/api/admin/users")
    assert response.status_code == 200
    rows = response.get_json()
    assert len(rows) == 2
    admin = next(row for row in rows if row["email"] == ADMIN_EMAIL)
    assert admin["admin"] is True
    assert admin["name"] == "Thomas Transfer"
    assert "password_hash" not in admin
    assert "created_at" in admin
    customer = next(row for row in rows if row["email"] == "jane@example.com")
    assert customer["admin"] is False


def test_admin_messages_and_comments_reflect_submissions(client):
    assert api_post(
        client,
        "/api/contact",
        {
            "name": "Alice",
            "email": "alice@example.com",
            "phone": "",
            "service": "Airport Transfer",
            "message": "Please call me.",
        },
    ).status_code == 201
    assert api_post(
        client,
        "/api/comment",
        {"name": "Bob", "rating": 5, "text": "Great driver."},
    ).status_code == 201
    assert login_admin(client).status_code == 200

    messages = client.get("/api/admin/messages").get_json()
    assert len(messages) == 1
    assert messages[0]["name"] == "Alice"
    assert messages[0]["service"] == "Airport Transfer"
    assert messages[0]["message"] == "Please call me."

    comments = client.get("/api/admin/comments").get_json()
    assert len(comments) == 1
    assert comments[0]["name"] == "Bob"
    assert comments[0]["rating"] == 5
    assert comments[0]["text"] == "Great driver."


def submit_message(client):
    response = api_post(
        client,
        "/api/contact",
        {
            "name": "Alice",
            "email": "alice@example.com",
            "phone": "",
            "service": "Airport Transfer",
            "message": "Please call me.",
        },
    )
    assert response.status_code == 201


def test_message_handled_flag_and_delete(client):
    submit_message(client)
    assert login_admin(client).status_code == 200

    messages = client.get("/api/admin/messages").get_json()
    assert messages[0]["handled"] is False
    message_id = messages[0]["id"]

    marked = api_post(client, f"/api/admin/messages/{message_id}/handled", {"handled": True})
    assert marked.status_code == 200
    assert marked.get_json() == {"ok": True, "handled": True}
    assert client.get("/api/admin/messages").get_json()[0]["handled"] is True

    reopened = api_post(client, f"/api/admin/messages/{message_id}/handled", {"handled": False})
    assert reopened.status_code == 200
    assert client.get("/api/admin/messages").get_json()[0]["handled"] is False

    bad = api_post(client, f"/api/admin/messages/{message_id}/handled", {"handled": "yes"})
    assert bad.status_code == 400
    missing = api_post(client, "/api/admin/messages/9999/handled", {"handled": True})
    assert missing.status_code == 404

    assert api_delete(client, f"/api/admin/messages/{message_id}").status_code == 200
    assert client.get("/api/admin/messages").get_json() == []
    assert api_delete(client, f"/api/admin/messages/{message_id}").status_code == 404


def test_admin_comment_delete(client):
    assert api_post(
        client, "/api/comment", {"name": "Bob", "rating": 5, "text": "Great driver."}
    ).status_code == 201
    assert login_admin(client).status_code == 200

    comment_id = client.get("/api/admin/comments").get_json()[0]["id"]
    assert api_delete(client, f"/api/admin/comments/{comment_id}").status_code == 200
    assert client.get("/api/admin/comments").get_json() == []
    assert api_delete(client, f"/api/admin/comments/{comment_id}").status_code == 404


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("post", "/api/admin/messages/1/handled"),
        ("delete", "/api/admin/messages/1"),
        ("delete", "/api/admin/comments/1"),
        ("post", "/api/admin/cars"),
        ("patch", "/api/admin/cars/1"),
        ("delete", "/api/admin/cars/1"),
        ("post", "/api/admin/users/1/active"),
        ("post", "/api/admin/users/1/password"),
        ("patch", "/api/bookings/1"),
        ("post", "/api/admin/bookings/1/payment"),
        ("post", "/api/admin/fares"),
        ("patch", "/api/admin/fares/1"),
        ("delete", "/api/admin/fares/1"),
    ],
)
def test_admin_write_endpoints_require_login(client, method, url):
    if method == "post":
        payload = {"handled": True} if "messages" in url else {}
        assert api_post(client, url, payload).status_code == 401
    elif method == "patch":
        assert api_patch(client, url, {"price": "1"}).status_code == 401
    else:
        assert api_delete(client, url).status_code == 401


@pytest.mark.parametrize(
    ("method", "url"),
    [
        ("post", "/api/admin/messages/1/handled"),
        ("delete", "/api/admin/messages/1"),
        ("delete", "/api/admin/comments/1"),
        ("post", "/api/admin/cars"),
        ("patch", "/api/admin/cars/1"),
        ("delete", "/api/admin/cars/1"),
        ("post", "/api/admin/users/1/active"),
        ("post", "/api/admin/users/1/password"),
        ("patch", "/api/bookings/1"),
        ("post", "/api/admin/bookings/1/payment"),
        ("post", "/api/admin/fares"),
        ("patch", "/api/admin/fares/1"),
        ("delete", "/api/admin/fares/1"),
    ],
)
def test_admin_write_endpoints_reject_customers(client, method, url):
    assert register_customer(client).status_code == 201
    if method == "post":
        payload = {"handled": True} if "messages" in url else {}
        assert api_post(client, url, payload).status_code == 403
    elif method == "patch":
        assert api_patch(client, url, {"price": "1"}).status_code == 403
    else:
        assert api_delete(client, url).status_code == 403


def test_startup_migrates_old_messages_table(tmp_path):
    """A database created before the `handled` column gains it on first start."""
    db_path = tmp_path / "old-schema.db"
    connection = sqlite3.connect(db_path)
    connection.execute(
        "CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " name TEXT NOT NULL, email TEXT NOT NULL, phone TEXT NOT NULL DEFAULT '',"
        " service TEXT NOT NULL DEFAULT '', message TEXT NOT NULL,"
        " created_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    connection.execute(
        "INSERT INTO messages (name, email, message) VALUES ('Old', 'old@example.com', 'Hello')"
    )
    connection.commit()
    connection.close()

    app = create_app(
        database=str(db_path),
        secret_key="test-secret",
        admin_password=ADMIN_PASSWORD,
    )
    admin = app.test_client()
    assert login_admin(admin).status_code == 200

    messages = admin.get("/api/admin/messages").get_json()
    assert len(messages) == 1
    assert messages[0]["name"] == "Old"
    assert messages[0]["handled"] is False


def test_startup_backfills_car_display_columns(tmp_path):
    """A fleet created before capacity/price/week/specs gets the seeded values."""
    db_path = tmp_path / "old-cars.db"
    connection = sqlite3.connect(db_path)
    connection.execute(
        "CREATE TABLE cars (id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " name TEXT NOT NULL, type TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',"
        " image TEXT NOT NULL DEFAULT '',"
        " status TEXT NOT NULL DEFAULT 'available',"
        " created_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    connection.execute(
        "INSERT INTO cars (name, type, image) VALUES"
        " ('Toyota Corolla Hybrid', 'Economy sedan', '/assets/images/cars/01.jpg')"
    )
    connection.commit()
    connection.close()

    app = create_app(
        database=str(db_path),
        secret_key="test-secret",
        admin_password=ADMIN_PASSWORD,
    )
    admin = app.test_client()
    assert login_admin(admin).status_code == 200

    cars = admin.get("/api/cars").get_json()
    assert cars[0]["capacity"] == 4
    assert cars[0]["price"] == "45,000 RWF"
    assert cars[0]["specs"] == ["5 seats · A/C · Hybrid", "Excellent fuel economy"]


def test_admin_car_create_update_delete(client):
    assert login_admin(client).status_code == 200

    created = api_post(
        client,
        "/api/admin/cars",
        {
            "name": "Test Coaster",
            "type": "Van",
            "description": "Roomy minibus.",
            "image": "/assets/images/cars/coaster.jpg",
            "capacity": 18,
            "price": "90,000 RWF",
            "week": "63,000 RWF/day from 7 days",
            "specs": "18 seats · A/C\nGreat for groups",
        },
    )
    assert created.status_code == 201
    car = created.get_json()["car"]
    assert car["capacity"] == 18
    assert car["specs"] == ["18 seats · A/C", "Great for groups"]
    assert car["status"] == "available"

    listed = client.get("/api/cars").get_json()
    assert listed[-1]["id"] == car["id"]
    assert listed[-1]["price"] == "90,000 RWF"

    updated = api_patch(client, f"/api/admin/cars/{car['id']}", {"price": "95,000 RWF"})
    assert updated.status_code == 200
    assert updated.get_json()["car"]["price"] == "95,000 RWF"
    # Untouched fields survive a partial update.
    assert updated.get_json()["car"]["capacity"] == 18

    assert api_delete(client, f"/api/admin/cars/{car['id']}").status_code == 200
    assert car["id"] not in [row["id"] for row in client.get("/api/cars").get_json()]


def test_admin_car_validation(client):
    assert login_admin(client).status_code == 200

    assert api_post(client, "/api/admin/cars", {"name": "", "type": "Van"}).status_code == 400
    assert api_post(client, "/api/admin/cars", {"name": "N", "type": ""}).status_code == 400
    assert api_post(
        client, "/api/admin/cars", {"name": "N", "type": "T", "capacity": "abc"}
    ).status_code == 400
    assert api_post(
        client, "/api/admin/cars", {"name": "N", "type": "T", "capacity": 0}
    ).status_code == 400
    assert api_patch(client, "/api/admin/cars/1", {}).status_code == 400
    assert api_patch(
        client, "/api/admin/cars/1", {"capacity": 99}
    ).status_code == 400
    assert api_patch(
        client, "/api/admin/cars/9999", {"price": "1"}
    ).status_code == 404
    assert api_delete(client, "/api/admin/cars/9999").status_code == 404


def test_car_capacity_is_checked_on_booking(client):
    assert login_admin(client).status_code == 200
    created = api_post(
        client, "/api/admin/cars", {"name": "Tiny", "type": "Economy sedan", "capacity": 2}
    )
    car_id = created.get_json()["car"]["id"]

    response = api_post(
        client,
        "/api/bookings",
        {
            "car_id": car_id,
            "pickup": "Airport",
            "dropoff": "Downtown",
            "trip_at": "2030-05-01T09:00",
            "passengers": 3,
        },
    )
    assert response.status_code == 400
    assert "up to 2 passengers" in response.get_json()["error"]

    ok = api_post(
        client,
        "/api/bookings",
        {
            "car_id": car_id,
            "pickup": "Airport",
            "dropoff": "Downtown",
            "trip_at": "2030-05-01T09:00",
            "passengers": 2,
        },
    )
    assert ok.status_code == 201


def test_car_with_bookings_cannot_be_deleted(client):
    assert login_admin(client).status_code == 200
    booking = api_post(
        client,
        "/api/bookings",
        {
            "car_id": 1,
            "pickup": "Airport",
            "dropoff": "Downtown",
            "trip_at": "2030-05-01T09:00",
            "passengers": 2,
        },
    )
    assert booking.status_code == 201
    assert api_delete(client, "/api/admin/cars/1").status_code == 409
    # Unbooked fleet cars remain deletable.
    assert api_delete(client, "/api/admin/cars/8").status_code == 200


def test_admin_creates_booking_for_customer(client):
    created = register_customer(client)
    assert created.status_code == 201
    user_id = created.get_json()["user"]["id"]

    admin = client.application.test_client()
    assert login_admin(admin).status_code == 200
    booking = api_post(
        admin,
        "/api/bookings",
        {
            "user_id": user_id,
            "car_id": 2,
            "pickup": "Airport",
            "dropoff": "Hotel",
            "trip_at": "2030-06-01T08:00",
            "passengers": 4,
        },
    )
    assert booking.status_code == 201
    booking_id = booking.get_json()["id"]

    rows = admin.get("/api/bookings").get_json()
    row = next(r for r in rows if r["id"] == booking_id)
    assert row["customer"] == "Jane Doe"
    assert row["car_id"] == 2

    # The car is taken, and Jane sees the trip that was made for her.
    free_ids = [c["id"] for c in admin.get("/api/cars?available=1").get_json()]
    assert 2 not in free_ids
    jane_rows = client.get("/api/bookings").get_json()
    assert jane_rows[0]["pickup"] == "Airport"


def test_customer_user_id_is_ignored_on_booking(client):
    assert register_customer(client).status_code == 201
    own_id = client.get("/api/me").get_json()["user"]["id"]
    booking = api_post(
        client,
        "/api/bookings",
        {
            "user_id": 9999,
            "car_id": 1,
            "pickup": "Airport",
            "dropoff": "Mall",
            "trip_at": "2030-06-01T08:00",
            "passengers": 1,
        },
    )
    assert booking.status_code == 201
    row = client.get("/api/bookings").get_json()[0]
    assert row["user_id"] == own_id


def test_admin_booking_edit_moves_car(client):
    assert login_admin(client).status_code == 200
    created = api_post(
        client,
        "/api/bookings",
        {
            "car_id": 3,
            "pickup": "Airport",
            "dropoff": "Station",
            "trip_at": "2030-06-01T08:00",
            "passengers": 3,
        },
    )
    assert created.status_code == 201
    booking_id = created.get_json()["id"]

    updated = api_patch(
        client,
        f"/api/bookings/{booking_id}",
        {"dropoff": "Hotel", "passengers": 5, "car_id": 2},
    )
    assert updated.status_code == 200
    row = next(r for r in client.get("/api/bookings").get_json() if r["id"] == booking_id)
    assert row["dropoff"] == "Hotel"
    assert row["passengers"] == 5
    assert row["car_id"] == 2

    free_ids = [c["id"] for c in client.get("/api/cars?available=1").get_json()]
    assert 3 in free_ids
    assert 2 not in free_ids


def test_admin_booking_edit_validation(client):
    assert login_admin(client).status_code == 200
    created = api_post(
        client,
        "/api/bookings",
        {
            "car_id": 1,
            "pickup": "Airport",
            "dropoff": "Downtown",
            "trip_at": "2030-06-01T08:00",
            "passengers": 2,
        },
    )
    booking_id = created.get_json()["id"]

    assert api_patch(client, f"/api/bookings/{booking_id}", {"passengers": 9}).status_code == 400
    past = api_patch(client, f"/api/bookings/{booking_id}", {"trip_at": "2020-01-01T10:00"})
    assert past.status_code == 400
    same = api_patch(client, f"/api/bookings/{booking_id}", {"dropoff": "Airport"})
    assert same.status_code == 400
    assert api_patch(client, f"/api/bookings/{booking_id}", {}).status_code == 400
    assert api_patch(client, "/api/bookings/9999", {"notes": "x"}).status_code == 404

    customer = client.application.test_client()
    assert register_customer(customer).status_code == 201
    assert api_patch(customer, f"/api/bookings/{booking_id}", {"notes": "x"}).status_code == 403


def make_booking(client, car_id=1, passengers=2):
    response = api_post(
        client,
        "/api/bookings",
        {
            "car_id": car_id,
            "pickup": "Airport",
            "dropoff": "Downtown",
            "trip_at": "2030-06-01T08:00",
            "passengers": passengers,
        },
    )
    assert response.status_code == 201
    return response.get_json()["id"]


def test_admin_records_payment_and_report(client):
    assert login_admin(client).status_code == 200
    booking_id = make_booking(client)

    paid = api_post(
        client,
        f"/api/admin/bookings/{booking_id}/payment",
        {"amount": 45000, "method": "MTN MoMo"},
    )
    assert paid.status_code == 200
    assert paid.get_json()["paid_amount"] == 45000

    row = next(r for r in client.get("/api/bookings").get_json() if r["id"] == booking_id)
    assert row["paid_amount"] == 45000
    assert row["paid_method"] == "MTN MoMo"
    assert row["paid_at"]

    report = client.get("/api/report").get_json()
    assert report["revenue"] == {"total": 45000.0, "paid_bookings": 1}

    cleared = api_post(
        client, f"/api/admin/bookings/{booking_id}/payment", {"amount": 0, "method": ""}
    )
    assert cleared.status_code == 200
    row = next(r for r in client.get("/api/bookings").get_json() if r["id"] == booking_id)
    assert row["paid_amount"] == 0
    assert row["paid_at"] == ""

    bad_amount = api_post(
        client, f"/api/admin/bookings/{booking_id}/payment", {"amount": "abc"}
    )
    assert bad_amount.status_code == 400
    negative = api_post(
        client, f"/api/admin/bookings/{booking_id}/payment", {"amount": -5, "method": "Cash"}
    )
    assert negative.status_code == 400
    no_method = api_post(
        client, f"/api/admin/bookings/{booking_id}/payment", {"amount": 1000, "method": ""}
    )
    assert no_method.status_code == 400
    missing = api_post(
        client, "/api/admin/bookings/9999/payment", {"amount": 10, "method": "Cash"}
    )
    assert missing.status_code == 404


def test_payment_on_cancelled_booking_is_rejected(client):
    assert login_admin(client).status_code == 200
    booking_id = make_booking(client)
    cancel = api_post(client, f"/api/bookings/{booking_id}/status", {"status": "cancelled"})
    assert cancel.status_code == 200
    payment = api_post(
        client, f"/api/admin/bookings/{booking_id}/payment", {"amount": 5000, "method": "Cash"}
    )
    assert payment.status_code == 400


def test_startup_migrates_booking_payments(tmp_path):
    """Bookings created before the paid columns can record payments after startup."""
    db_path = tmp_path / "old-bookings.db"
    connection = sqlite3.connect(db_path)
    connection.execute(
        "CREATE TABLE bookings (id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,"
        " car_id INTEGER NOT NULL REFERENCES cars(id),"
        " pickup TEXT NOT NULL, dropoff TEXT NOT NULL, trip_at TEXT NOT NULL,"
        " passengers INTEGER NOT NULL, notes TEXT NOT NULL DEFAULT '',"
        " status TEXT NOT NULL DEFAULT 'pending'"
        " CHECK (status IN ('pending','confirmed','completed','cancelled')),"
        " created_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    connection.commit()
    connection.close()

    app = create_app(
        database=str(db_path),
        secret_key="test-secret",
        admin_password=ADMIN_PASSWORD,
    )
    client = app.test_client()
    assert login_admin(client).status_code == 200
    booking_id = make_booking(client)
    paid = api_post(
        client, f"/api/admin/bookings/{booking_id}/payment", {"amount": 3000, "method": "Cash"}
    )
    assert paid.status_code == 200
    report = client.get("/api/report").get_json()
    assert report["revenue"]["total"] == 3000.0


def test_admin_export_bookings_csv(client):
    assert login_admin(client).status_code == 200
    booking_id = make_booking(client)

    response = client.get("/api/admin/export/bookings.csv")
    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    text = response.get_data(as_text=True)
    assert text.startswith("\ufeff")
    lines = text.lstrip("\ufeff").splitlines()
    assert lines[0].startswith("id,customer,email")
    assert lines[1].split(",")[0] == str(booking_id)
    assert "Thomas Transfer" in lines[1]
    assert len(lines) == 2  # only the one booking


def test_admin_export_messages_csv_quotes_commas(client):
    assert api_post(
        client,
        "/api/contact",
        {
            "name": "Alice",
            "email": "alice@example.com",
            "phone": "",
            "service": "Tours, city",
            "message": "Yes, please call.",
        },
    ).status_code == 201
    assert login_admin(client).status_code == 200

    response = client.get("/api/admin/export/messages.csv")
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert '"Tours, city"' in text
    assert '"Yes, please call."' in text
    lines = text.lstrip("\ufeff").splitlines()
    assert "handled" in lines[0]
    assert ",no," in lines[1]  # message is still unhandled


def test_admin_role_toggle_grants_and_revokes(client):
    created = register_customer(client).get_json()["user"]
    user_id = created["id"]
    assert login_admin(client).status_code == 200

    granted = api_post(
        client, f"/api/admin/users/{user_id}/admin", {"admin": True}
    )
    assert granted.status_code == 200
    assert granted.get_json()["user"]["admin"] is True
    assert any(
        row["admin"] for row in client.get("/api/admin/users").get_json()
        if row["id"] == user_id
    )

    revoked = api_post(
        client, f"/api/admin/users/{user_id}/admin", {"admin": False}
    )
    assert revoked.status_code == 200
    assert revoked.get_json()["user"]["admin"] is False


def test_admin_role_toggle_validation(client):
    assert login_admin(client).status_code == 200
    own_id = client.get("/api/me").get_json()["user"]["id"]

    assert api_post(
        client, f"/api/admin/users/{own_id}/admin", {"admin": False}
    ).status_code == 400
    assert api_post(
        client, f"/api/admin/users/{own_id}/admin", {"admin": "false"}
    ).status_code == 400
    assert api_post(
        client, "/api/admin/users/9999/admin", {"admin": True}
    ).status_code == 404
    assert api_post(
        client, f"/api/admin/users/{own_id}/admin", {"admin": True}
    ).status_code == 200

    # A non-admin cannot call the toggle, even on their own account.
    assert register_customer(client, email="other@example.com").status_code == 201
    other_id = client.get("/api/me").get_json()["user"]["id"]
    assert api_post(
        client, f"/api/admin/users/{other_id}/admin", {"admin": True}
    ).status_code == 403


def test_second_admin_can_be_promoted_and_demoted(client):
    assert login_admin(client).status_code == 200
    original_id = client.get("/api/me").get_json()["user"]["id"]

    second = register_customer(client).get_json()["user"]
    assert login_admin(client).status_code == 200
    assert api_post(
        client, f"/api/admin/users/{second['id']}/admin", {"admin": True}
    ).status_code == 200

    # The second admin may demote the original, but never themselves.
    assert api_post(
        client,
        "/api/login",
        {"email": "jane@example.com", "password": "secret123"},
    ).status_code == 200
    assert api_post(
        client, f"/api/admin/users/{original_id}/admin", {"admin": False}
    ).status_code == 200
    assert api_post(
        client, f"/api/admin/users/{second['id']}/admin", {"admin": False}
    ).status_code == 400
    assert [r for r in client.get("/api/admin/users").get_json() if r["admin"]] == [
        r for r in client.get("/api/admin/users").get_json()
        if r["id"] == second["id"]
    ]


def test_admin_deactivate_and_activate(client):
    assert register_customer(client).status_code == 201
    user_id = client.get("/api/me").get_json()["user"]["id"]

    admin = client.application.test_client()
    assert login_admin(admin).status_code == 200
    rows = admin.get("/api/admin/users").get_json()
    assert next(row for row in rows if row["id"] == user_id)["active"] is True

    assert api_post(
        admin, f"/api/admin/users/{user_id}/active", {"active": False}
    ).status_code == 200

    # The customer's existing session is now treated as signed out...
    assert client.get("/api/me").get_json()["user"] is None
    # ...and a fresh login is rejected until an admin reactivates them.
    fresh = client.application.test_client()
    blocked = api_post(
        fresh, "/api/login", {"email": "jane@example.com", "password": "secret123"}
    )
    assert blocked.status_code == 401
    assert "deactivated" in blocked.get_json()["error"]

    rows = admin.get("/api/admin/users").get_json()
    assert next(row for row in rows if row["id"] == user_id)["active"] is False

    assert api_post(
        admin, f"/api/admin/users/{user_id}/active", {"active": True}
    ).status_code == 200
    assert api_post(
        fresh, "/api/login", {"email": "jane@example.com", "password": "secret123"}
    ).status_code == 200


def test_admin_account_guards(client):
    assert login_admin(client).status_code == 200
    own_id = client.get("/api/me").get_json()["user"]["id"]

    assert api_post(
        client, f"/api/admin/users/{own_id}/active", {"active": False}
    ).status_code == 400
    assert api_post(
        client, f"/api/admin/users/{own_id}/active", {"active": "no"}
    ).status_code == 400
    assert api_post(
        client, "/api/admin/users/9999/active", {"active": False}
    ).status_code == 404
    assert api_post(
        client, f"/api/admin/users/{own_id}/password", {"password": "short"}
    ).status_code == 400
    assert api_post(
        client, "/api/admin/users/9999/password", {"password": "longenough"}
    ).status_code == 404


def test_admin_password_reset(client):
    assert register_customer(client).status_code == 201
    user_id = client.get("/api/me").get_json()["user"]["id"]

    admin = client.application.test_client()
    assert login_admin(admin).status_code == 200
    assert api_post(
        admin, f"/api/admin/users/{user_id}/password", {"password": "brand-new-pass"}
    ).status_code == 200

    customer = client.application.test_client()
    assert api_post(
        customer, "/api/login", {"email": "jane@example.com", "password": "secret123"}
    ).status_code == 401
    assert api_post(
        customer, "/api/login", {"email": "jane@example.com", "password": "brand-new-pass"}
    ).status_code == 200


def test_startup_migrates_users_table(tmp_path):
    """Accounts created before the `active` column stay usable after startup."""
    db_path = tmp_path / "old-users.db"
    connection = sqlite3.connect(db_path)
    connection.execute(
        "CREATE TABLE users (id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " first_name TEXT NOT NULL, last_name TEXT NOT NULL,"
        " email TEXT NOT NULL UNIQUE COLLATE NOCASE,"
        " phone TEXT NOT NULL DEFAULT '', password_hash TEXT NOT NULL,"
        " is_admin INTEGER NOT NULL DEFAULT 0,"
        " created_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    connection.commit()
    connection.close()

    app = create_app(
        database=str(db_path),
        secret_key="test-secret",
        admin_password=ADMIN_PASSWORD,
    )
    admin = app.test_client()
    assert login_admin(admin).status_code == 200
    rows = admin.get("/api/admin/users").get_json()
    assert rows and all(row["active"] is True for row in rows)


def test_pay_page_renders_seeded_fares(client):
    page = client.get("/pay")
    assert page.status_code == 200
    assert b"25,000 RWF" in page.data
    assert b"$315" in page.data
    assert b'data-svc="airport"' in page.data
    assert b'data-flw=""' in page.data


def test_admin_fares_crud_and_visibility(client):
    assert login_admin(client).status_code == 200

    rows = client.get("/api/admin/fares").get_json()
    assert len(rows) == 7
    assert rows[0]["key"] == "airport"
    assert rows[0]["price"] == "25,000 RWF"
    assert rows[0]["active"] is True

    created = api_post(
        client,
        "/api/admin/fares",
        {
            "key": "gishwati",
            "tag": "Tour",
            "name": "Gishwati Forest",
            "amount": 180,
            "currency": "USD",
            "note": "Per person",
            "flw_link": "https://flutterwave.com/pay/gishwati",
        },
    )
    assert created.status_code == 201
    fare = created.get_json()["fare"]
    assert fare["price"] == "$180"
    assert fare["flw_link"] == "https://flutterwave.com/pay/gishwati"

    assert b'data-svc="gishwati"' in client.get("/pay").data

    updated = api_patch(client, f"/api/admin/fares/{fare['id']}", {"amount": 160})
    assert updated.status_code == 200
    assert updated.get_json()["fare"]["price"] == "$160"

    hidden = api_patch(client, f"/api/admin/fares/{fare['id']}", {"active": False})
    assert hidden.get_json()["fare"]["active"] is False
    assert b'data-svc="gishwati"' not in client.get("/pay").data

    assert api_delete(client, f"/api/admin/fares/{fare['id']}").status_code == 200
    assert len(client.get("/api/admin/fares").get_json()) == 7


def test_admin_fare_validation(client):
    assert login_admin(client).status_code == 200

    bad = api_post(client, "/api/admin/fares",
                   {"key": "Bad Key!", "name": "X", "amount": 5})
    assert bad.status_code == 400
    no_name = api_post(client, "/api/admin/fares", {"key": "ok", "name": "", "amount": 5})
    assert no_name.status_code == 400
    zero = api_post(client, "/api/admin/fares", {"key": "ok", "name": "X", "amount": 0})
    assert zero.status_code == 400
    bad_currency = api_post(
        client, "/api/admin/fares", {"key": "ok", "name": "X", "amount": 5, "currency": "EUR"}
    )
    assert bad_currency.status_code == 400
    bad_link = api_post(
        client, "/api/admin/fares",
        {"key": "ok", "name": "X", "amount": 5, "flw_link": "http://insecure.example"},
    )
    assert bad_link.status_code == 400
    duplicate = api_post(client, "/api/admin/fares", {"key": "airport", "name": "X", "amount": 5})
    assert duplicate.status_code == 409
    assert api_patch(client, "/api/admin/fares/1", {}).status_code == 400
    assert api_patch(client, "/api/admin/fares/9999", {"amount": 5}).status_code == 404
    assert api_delete(client, "/api/admin/fares/9999").status_code == 404


def test_admin_page_guards(client):
    assert client.get("/admin").status_code == 302
    assert client.get("/admin").headers["Location"] == "/account#login"

    assert register_customer(client).status_code == 201
    response = client.get("/admin")
    assert response.status_code == 302
    assert response.headers["Location"] == "/account"

    assert login_admin(client).status_code == 200
    page = client.get("/admin")
    assert page.status_code == 200
    assert b"Admin" in page.data
    assert b"/js/admin.js" in page.data
    assert b"Admin sections" in page.data
    assert b'class="nav-admin-item"' in page.data
    assert b'href="/admin" aria-current="page"' in page.data
    assert b'data-view="comments"' in page.data
    assert b'data-view="fares"' in page.data
    assert b'id="messages-status"' in page.data
    assert client.get("/js/admin.js").status_code == 200
