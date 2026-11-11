"""Marketing pages and the account shell.

The JSON API still lives in ``backend/app.py``. These routes only render
templates. ``/account`` intentionally stays a single document with hash
sections because ``web/js/dashboard.js`` and ``web/js/auth-forms.js`` expect
all of their forms and tables to exist on one page.
"""

import hashlib

from flask import (
    Blueprint,
    abort,
    make_response,
    redirect,
    render_template,
    request,
    session,
)

try:
    from .db import get_db
except ImportError:  # pragma: no cover
    from backend.db import get_db

pages = Blueprint("pages", __name__)

# Real routes under /admin/<view>; keep in sync with the nav in
# ``pages/admin.html`` and the bookmark map in ``web/js/legacy-hash.js``.
ADMIN_VIEWS = (
    "overview", "bookings", "fleet", "accounts", "messages", "comments",
    "fares",
)

PAGE_META = {
    "home": (
        "Thomas Transfer — Kigali transfers and car rental",
        "Airport transfers, city rides, intercity travel and car rental in "
        "Kigali, Rwanda. Fixed prices and professional drivers, 24/7.",
    ),
    "transport": (
        "Transport services — Thomas Transfer",
        "Airport pickups, full-day Kigali service and private intercity "
        "travel across Rwanda with fixed prices and professional drivers.",
    ),
    "tours": (
        "Tour packages — Thomas Transfer",
        "Private tours to Akagera, Volcanoes, Nyungwe and Lake Kivu with a "
        "car and a driver-guide who knows the roads.",
    ),
    "cars": (
        "Car rental — Thomas Transfer",
        "Rent a well-maintained SUV, sedan or van in Kigali by the day, with "
        "30% off rentals of a week or longer.",
    ),
    "contact": (
        "Contact — Thomas Transfer",
        "Talk to Thomas Transfer in Kigali by WhatsApp, phone or email. "
        "Airport transfers are available 24 hours a day.",
    ),
    "pay": (
        "Pay online — Thomas Transfer",
        "Pay a set fare or a custom amount securely by Visa or Mastercard. "
        "Card details are handled by Flutterwave.",
    ),
    "comment": (
        "Comment — Thomas Transfer",
        "Tell us about your trip. Comments are private and read only by the "
        "Thomas Transfer team.",
    ),
    "account": (
        "Your account — Thomas Transfer",
        "Log in to book a car, see your bookings and manage your Thomas "
        "Transfer account.",
    ),
    "forgot": (
        "Forgot password — Thomas Transfer",
        "Request a password reset link for your Thomas Transfer account.",
    ),
    "reset": (
        "Choose a new password — Thomas Transfer",
        "Set a new password for your Thomas Transfer account.",
    ),
    "admin": (
        "Admin — Thomas Transfer",
        "Manage bookings, fleet status, accounts, messages and feedback.",
    ),
}


def render_page(name, **extra):
    title, description = PAGE_META[name]
    return render_template(
        f"pages/{name}.html",
        page=name,
        page_title=title,
        page_description=description,
        **extra,
    )


def format_price(amount, currency):
    """Display text for a fare or car price, e.g. '25,000 RWF' or '$315'."""
    if currency == "USD":
        return "${:,.0f}".format(amount)
    return "{:,.0f} RWF".format(amount)


# ---------------------------------------------------------------------------
# Marketing pages
# ---------------------------------------------------------------------------


@pages.get("/")
def home():
    return render_page("home")


@pages.get("/transport")
def transport():
    return render_page("transport")


@pages.get("/tours")
def tours():
    return render_page("tours")


@pages.get("/cars")
def cars():
    rows = get_db().execute(
        "SELECT id, name, type, description, image, status,"
        " capacity, price, week, specs FROM cars ORDER BY id"
    ).fetchall()
    cards = []
    for row in rows:
        card = dict(row)
        card["specs"] = [line for line in card["specs"].split("\n") if line]
        cards.append(card)
    return render_page("cars", cars=cards)


@pages.get("/contact")
def contact():
    return render_page("contact")


@pages.get("/pay")
def pay():
    rows = get_db().execute(
        "SELECT key, tag, name, amount, currency, note, flw_link FROM fares"
        " WHERE active = 1 ORDER BY id"
    ).fetchall()
    fares = []
    for row in rows:
        fare = dict(row)
        fare["price"] = format_price(fare["amount"], fare["currency"])
        fares.append(fare)
    return render_page("pay", fares=fares)


@pages.get("/comment")
def comment():
    return render_page("comment")


# ---------------------------------------------------------------------------
# Account shell
# ---------------------------------------------------------------------------


@pages.get("/account")
def account():
    return render_page("account")


@pages.get("/forgot")
def forgot_password():
    return _auth_page(render_page("forgot"))


@pages.get("/reset")
def reset_password():
    token = (request.args.get("token") or "").strip()
    valid = False
    if token:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        valid = (
            get_db()
            .execute(
                "SELECT 1 FROM password_resets WHERE token_hash = ?"
                " AND used_at IS NULL AND expires_at > datetime('now')",
                (digest,),
            )
            .fetchone()
            is not None
        )
    return _auth_page(
        render_page("reset", reset_token=token if valid else "", reset_valid=valid)
    )


def _auth_page(response):
    """Keep reset pages out of caches and search indexes."""
    response = make_response(response)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex"
    return response


def _session_user():
    """Return the signed-in user's id/admin flag without importing app.py."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = get_db().execute(
        "SELECT id, is_admin, token_version FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if user is None:
        return None
    if session.get("token_version", 0) != user["token_version"]:
        # Signed out by a password reset in another session.
        return None
    return user


def _admin_gate():
    """Return a redirect response when the visitor may not see the portal."""
    user = _session_user()
    if user is None:
        return redirect("/account#login", code=302)
    if not user["is_admin"]:
        return redirect("/account", code=302)
    return None


@pages.get("/admin")
def admin():
    blocked = _admin_gate()
    if blocked is not None:
        return blocked
    return render_page("admin", view="overview")


@pages.get("/admin/<view>")
def admin_view(view):
    blocked = _admin_gate()
    if blocked is not None:
        return blocked
    if view not in ADMIN_VIEWS:
        abort(404)
    return render_page("admin", view=view)


# ---------------------------------------------------------------------------
# Old hash links, now real bookmarks. Fragments never reach the server, so
# these aliases redirect and let the browser apply the hash.
# ---------------------------------------------------------------------------


@pages.get("/login")
def login():
    return redirect("/account#login", code=302)


@pages.get("/register")
def register():
    return redirect("/account#create-account", code=302)


@pages.get("/car-list")
def car_list():
    return redirect("/account#car-list", code=302)


@pages.get("/available")
def available():
    return redirect("/account#available", code=302)


@pages.get("/bookings")
def bookings():
    return redirect("/account#bookings", code=302)


@pages.get("/report")
def report():
    return redirect("/account#report", code=302)


@pages.get("/logout")
def logout():
    return redirect("/account#logout", code=302)
