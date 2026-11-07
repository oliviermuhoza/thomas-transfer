"""Marketing pages and the account shell.

The JSON API still lives in ``backend/app.py``. These routes only render
templates. ``/account`` intentionally stays a single document with hash
sections because ``web/js/dashboard.js`` and ``web/js/auth-forms.js`` expect
all of their forms and tables to exist on one page.
"""

from flask import Blueprint, redirect, render_template

pages = Blueprint("pages", __name__)

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
}


def render_page(name):
    title, description = PAGE_META[name]
    return render_template(
        f"pages/{name}.html",
        page=name,
        page_title=title,
        page_description=description,
    )


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
    return render_page("cars")


@pages.get("/contact")
def contact():
    return render_page("contact")


@pages.get("/pay")
def pay():
    return render_page("pay")


@pages.get("/comment")
def comment():
    return render_page("comment")


# ---------------------------------------------------------------------------
# Account shell
# ---------------------------------------------------------------------------


@pages.get("/account")
def account():
    return render_page("account")


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
