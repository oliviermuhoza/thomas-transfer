import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app import create_app  # noqa: E402

ADMIN_PASSWORD = "admin-test-pass"


@pytest.fixture()
def client(tmp_path):
    app = create_app(
        database=str(tmp_path / "pages.db"),
        secret_key="test-secret",
        admin_password=ADMIN_PASSWORD,
    )
    return app.test_client()


PAGE_HEADINGS = {
    "/": b"Your ride is ready when you are.",
    "/transport": b"Arrive rested. <em>Every time.</em>",
    "/tours": b"Rwanda, remarkably close",
    "/cars": b"Your keys to <em>a thousand hills</em>",
    "/contact": b"We reply in <em>minutes</em>",
    "/pay": b"Pay by <em>card</em>",
    "/comment": b"Tell us about your trip.",
    "/account": b"Available cars",
    "/account#login": b"Sign in to your Thomas Transfer account.",
}


@pytest.mark.parametrize("url,heading", PAGE_HEADINGS.items())
def test_page_renders(client, url, heading):
    page = client.get(url)
    assert page.status_code == 200
    assert heading in page.data
    assert b"/css/styles.css" in page.data


def test_nav_active_page_is_marked(client):
    page = client.get("/transport")
    assert page.status_code == 200
    assert b'href="/transport" aria-current="page"' in page.data


def test_signed_in_header_shows_avatar(client):
    token = client.get("/api/csrf").get_json()["csrf_token"]
    registered = client.post(
        "/api/register",
        json={
            "first_name": "Ada",
            "last_name": "Doe",
            "email": "ada@example.com",
            "phone": "+250700000123",
            "password": "secret123",
        },
        headers={"X-CSRF-Token": token},
    )
    assert registered.status_code == 201

    page = client.get("/")
    assert b'class="logged-in' in page.data
    assert b'id="nav-user"' in page.data
    assert b'id="avatar-initials">AD<' in page.data
    assert b"Ada Doe" in page.data
    assert b"ada@example.com" in page.data
    assert b'id="avatar-menu"' in page.data
    assert b'aria-haspopup="menu"' in page.data


def test_account_loads_dashboard_scripts(client):
    page = client.get("/account")
    assert b"/js/dashboard.js" in page.data
    assert b"/js/auth-forms.js" in page.data
    assert b"/js/session.js" in page.data


def test_marketing_page_does_not_load_account_scripts(client):
    page = client.get("/")
    assert b"/js/dashboard.js" not in page.data
    assert b"/js/auth-forms.js" not in page.data
    assert b"/js/legacy-hash.js" in page.data


@pytest.mark.parametrize(
    "path,target",
    [
        ("/login", "/account#login"),
        ("/register", "/account#create-account"),
        ("/car-list", "/account#car-list"),
        ("/available", "/account#available"),
        ("/bookings", "/account#bookings"),
        ("/report", "/account#report"),
        ("/logout", "/account#logout"),
        ("/index.html", "/"),
    ],
)
def test_old_links_redirect(client, path, target):
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["Location"] == target


def test_unknown_page_is_404(client):
    response = client.get("/no-such-page")
    assert response.status_code == 404
    assert b"Page not found" in response.data


def test_static_assets_still_served(client):
    assert client.get("/css/styles.css").status_code == 200
    assert client.get("/js/session.js").status_code == 200
    assert client.get("/js/search.js").status_code == 200


def test_legacy_hash_routes_old_admin_bookmarks(client):
    # /admin#fleet bookmarks must reach the real route /admin/fleet, and the
    # account bookmark map must never rewrite unknown hashes on /admin.
    script = client.get("/js/legacy-hash.js").data.decode("utf-8")
    assert "location.pathname === '/admin'" in script
    assert "location.replace('/admin/' + name)" in script


def test_navbar_search_is_present_on_every_page(client):
    for url in ("/", "/account", "/cars"):
        page = client.get(url)
        assert page.status_code == 200
        assert b'id="site-search"' in page.data
        assert b'id="search-input"' in page.data
        assert b'id="search-results"' in page.data


def test_admin_copy_has_translation_keys():
    script = (
        Path(__file__).resolve().parents[2] / "web" / "js" / "i18n.js"
    ).read_text(encoding="utf-8")
    head = script[script.index("var RW = {") : script.index("};", script.index("var RW = {"))]
    required = [
        "Admin", "Overview", "Bookings", "Fleet", "Messages", "Operations",
        "At a glance", "Needs attention", "All bookings", "Filter by status",
        "No pending bookings.", "Please log in again to continue.",
        "Make admin", "Remove admin", "Search", "Search...", "Search results",
        "Loading...", "Account", "Name", "People", "Role", "Joined", "You",
    ]
    for key in required:
        assert '"' + key + '":' in head, f"missing i18n key: {key}"
