"""Password reset: email link, single use, expiry, session invalidation."""

import re
from urllib.parse import unquote

import pytest

import backend.app as backend_app
from backend.app import create_app
from backend.db import get_db

ADMIN_PASSWORD = "admin-test-pass"


@pytest.fixture()
def app(tmp_path):
    return create_app(
        database=str(tmp_path / "reset.db"),
        secret_key="test-secret",
        admin_password=ADMIN_PASSWORD,
        admin_email="admin@example.com",
    )


@pytest.fixture()
def client(app):
    return app.test_client()


def csrf_headers(client):
    return {"X-CSRF-Token": client.get("/api/csrf").get_json()["csrf_token"]}


def api_post(client, url, json=None):
    return client.post(url, json=json or {}, headers=csrf_headers(client))


def register(client, email="jane@example.com", password="secret123"):
    return api_post(
        client,
        "/api/register",
        {
            "first_name": "Jane",
            "last_name": "Doe",
            "email": email,
            "phone": "+250700000000",
            "password": password,
        },
    )


def login(client, email="jane@example.com", password="secret123"):
    return api_post(client, "/api/login", {"email": email, "password": password})


@pytest.fixture()
def outbox(monkeypatch):
    sent = []

    def fake_send(to, subject, body):
        sent.append({"to": to, "subject": subject, "body": body})

    monkeypatch.setattr(backend_app, "mail_configured", lambda: True)
    monkeypatch.setattr(backend_app, "send_email", fake_send)
    return sent


def reset_token(sent):
    link = re.search(r"https?://\S+/reset\?token=\S+", sent[-1]["body"]).group(0)
    return unquote(link.split("token=", 1)[1])


def request_reset(client, email="jane@example.com"):
    return api_post(client, "/api/password/forgot", {"email": email})


def test_forgot_sends_link_and_reset_changes_password(client, outbox):
    assert register(client).status_code == 201
    response = request_reset(client)
    assert response.status_code == 200
    message = response.get_json()["message"]
    assert "reset link" in message

    assert len(outbox) == 1
    assert outbox[0]["to"] == "jane@example.com"
    assert "Reset your Thomas Transfer password" == outbox[0]["subject"]
    token = reset_token(outbox)

    reset = api_post(client, "/api/password/reset", {"token": token, "password": "newsecret1"})
    assert reset.status_code == 200
    assert reset.get_json()["ok"] is True

    assert login(client, password="secret123").status_code == 401
    assert login(client, password="newsecret1").status_code == 200


def test_unknown_email_gets_the_same_answer(client, outbox):
    response = request_reset(client, email="nobody@example.com")
    assert response.status_code == 200
    assert "reset link" in response.get_json()["message"]
    assert outbox == []


def test_token_is_single_use(client, outbox):
    assert register(client).status_code == 201
    request_reset(client)
    token = reset_token(outbox)

    assert api_post(
        client, "/api/password/reset", {"token": token, "password": "newsecret1"}
    ).status_code == 200
    assert api_post(
        client, "/api/password/reset", {"token": token, "password": "another123"}
    ).status_code == 400


def test_expired_token_is_rejected(app, client, outbox):
    assert register(client).status_code == 201
    request_reset(client)
    token = reset_token(outbox)

    with app.app_context():
        db = get_db()
        db.execute("UPDATE password_resets SET expires_at = datetime('now', '-1 minute')")
        db.commit()

    response = api_post(
        client, "/api/password/reset", {"token": token, "password": "newsecret1"}
    )
    assert response.status_code == 400
    assert "invalid or has expired" in response.get_json()["error"]


def test_reset_signs_out_other_sessions(client, outbox):
    assert register(client).status_code == 201
    other = client.application.test_client()
    assert login(other).status_code == 200
    assert other.get("/api/me").get_json()["user"]["email"] == "jane@example.com"

    request_reset(client)
    token = reset_token(outbox)
    assert api_post(
        client, "/api/password/reset", {"token": token, "password": "newsecret1"}
    ).status_code == 200

    assert other.get("/api/me").get_json()["user"] is None
    assert other.get("/api/bookings").status_code == 401


def test_reset_validation(client):
    assert api_post(
        client, "/api/password/reset", {"token": "bogus", "password": "newsecret1"}
    ).status_code == 400
    assert api_post(
        client, "/api/password/reset", {"token": "bogus", "password": "short"}
    ).status_code == 400


def test_reset_signs_out_the_admin_portal(client, outbox):
    admin = client.application.test_client()
    assert login(admin, email="admin@example.com", password=ADMIN_PASSWORD).status_code == 200
    assert admin.get("/admin").status_code == 200

    request_reset(client, email="admin@example.com")
    token = reset_token(outbox)
    assert api_post(
        client, "/api/password/reset", {"token": token, "password": "newadmin123"}
    ).status_code == 200

    response = admin.get("/admin")
    assert response.status_code == 302
    assert response.headers["Location"] == "/account#login"
