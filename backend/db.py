"""SQLite helpers: connection handling, schema creation and initial seed data."""

import os
import secrets
import sqlite3
import sys
from pathlib import Path

from flask import current_app, g
from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
SCHEMA_PATH = BASE_DIR / "schema.sql"

# Mirrors the eight car cards on the static fleet page, in the same order.
# Fields: name, type, description, image, capacity, price, week, specs.
SEED_CARS = [
    (
        "Toyota Corolla Hybrid",
        "Economy sedan",
        "Economical and comfortable for city rides and airport trips.",
        "/assets/images/cars/01-toyota-corolla-hybrid.jpg",
        4,
        "45,000 RWF",
        "31,500 RWF/day from 7 days",
        "5 seats · A/C · Hybrid\nExcellent fuel economy",
    ),
    (
        "Toyota Land Cruiser",
        "Large SUV",
        "Strong and spacious for long distance and rough roads.",
        "/assets/images/cars/02-toyota-land-cruiser.jpg",
        7,
        "70,000 RWF",
        "49,000 RWF/day from 7 days",
        "7 seats · 4×4 · A/C\nBuilt for rough roads",
    ),
    (
        "Toyota RAV4",
        "Compact SUV",
        "Modern, smooth and good for small families.",
        "/assets/images/cars/03-toyota-rav4.jpg",
        5,
        "50,000 RWF",
        "35,000 RWF/day from 7 days",
        "4–5 seats · AWD · A/C\nGreat fuel economy",
    ),
    (
        "Mercedes-Benz G-Class",
        "Luxury SUV",
        "A premium ride for special occasions and VIP guests.",
        "/assets/images/cars/04-mercedes-benz-g-class.jpg",
        5,
        "150,000 RWF",
        "105,000 RWF/day from 7 days",
        "5 seats · AWD · A/C\nVIP comfort and presence",
    ),
    (
        "Volkswagen Transporter",
        "Van",
        "Roomy and comfortable for groups with luggage.",
        "/assets/images/cars/05-volkswagen-transporter.jpg",
        8,
        "120,000 RWF",
        "84,000 RWF/day from 7 days",
        "8–9 seats · A/C · large boot\nRoomy for groups and luggage",
    ),
    (
        "Mercedes-AMG GLE Coupe",
        "Luxury SUV",
        "A fast, stylish ride for executive travel.",
        "/assets/images/cars/06-mercedes-amg-gle-coupe.jpg",
        5,
        "150,000 RWF",
        "105,000 RWF/day from 7 days",
        "5 seats · AWD · A/C\nExecutive style and speed",
    ),
    (
        "Toyota Land Cruiser Prado, black",
        "Mid-size SUV",
        "A reliable all-round vehicle for family and business trips.",
        "/assets/images/cars/07-toyota-land-cruiser-prado-black.jpg",
        7,
        "70,000 RWF",
        "49,000 RWF/day from 7 days",
        "7 seats · AWD · A/C\nFamily and business trips",
    ),
    (
        "Toyota Land Cruiser Prado, black (rear view)",
        "Mid-size SUV",
        "Large luggage space and comfortable seating.",
        "/assets/images/cars/08-toyota-land-cruiser-prado-rear.jpg",
        7,
        "70,000 RWF",
        "49,000 RWF/day from 7 days",
        "7 seats · large luggage space\nComfortable seating",
    ),
]


# Standard fares shown on the /pay page (key, tag, name, amount, currency, note).
SEED_FARES = [
    ("airport", "Airport transfer", "Kigali Airport \u21c4 City", 25000, "RWF", "Fixed fare"),
    ("allday", "City transport", "Kigali All-Day Service", 150000, "RWF", "Until 21:00"),
    ("akagera", "Safari \u00b7 10% off", "Akagera National Park", 315, "USD", "Per person"),
    ("volcanoes", "Tour \u00b7 10% off", "Volcanoes National Park", 270, "USD", "Per person"),
    ("nyungwe", "Tour \u00b7 10% off", "Nyungwe National Park", 270, "USD", "Per person"),
    ("gisenyi", "Lake Kivu \u00b7 10% off", "Gisenyi \u2014 Lake Kivu", 225, "USD", "Per person"),
    ("palace", "Heritage \u00b7 10% off", "King's Palace Museum", 90, "USD", "Per person"),
]


def get_db():
    """Return the connection for the current request, opening it on first use."""
    if "db" not in g:
        connection = sqlite3.connect(current_app.config["DATABASE"])
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        g.db = connection
    return g.db


def close_db(exc=None):
    """Close the request connection (registered as a teardown handler)."""
    connection = g.pop("db", None)
    if connection is not None:
        connection.close()


def init_db(admin_password=None, production=False, ephemeral=False):
    """Create missing tables, apply additive migrations and seed data."""
    db = get_db()
    db.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    _migrate(db)
    _seed_cars(db)
    _seed_fares(db)
    _seed_admin(db, admin_password, production=production, ephemeral=ephemeral)
    db.commit()


def _seed_fares(db):
    if db.execute("SELECT 1 FROM fares LIMIT 1").fetchone():
        return
    db.executemany(
        "INSERT INTO fares (key, tag, name, amount, currency, note) VALUES (?, ?, ?, ?, ?, ?)",
        SEED_FARES,
    )


def _migrate(db):
    """Add columns that CREATE TABLE IF NOT EXISTS cannot add to old tables."""
    columns = {row["name"] for row in db.execute("PRAGMA table_info(messages)")}
    if "handled" not in columns:
        db.execute("ALTER TABLE messages ADD COLUMN handled INTEGER NOT NULL DEFAULT 0")

    comment_columns = {row["name"] for row in db.execute("PRAGMA table_info(comments)")}
    if "handled" not in comment_columns:
        db.execute("ALTER TABLE comments ADD COLUMN handled INTEGER NOT NULL DEFAULT 0")

    car_columns = {row["name"] for row in db.execute("PRAGMA table_info(cars)")}
    if "capacity" not in car_columns:
        db.execute("ALTER TABLE cars ADD COLUMN capacity INTEGER NOT NULL DEFAULT 4")
        db.execute("ALTER TABLE cars ADD COLUMN price TEXT NOT NULL DEFAULT ''")
        db.execute("ALTER TABLE cars ADD COLUMN week TEXT NOT NULL DEFAULT ''")
        db.execute("ALTER TABLE cars ADD COLUMN specs TEXT NOT NULL DEFAULT ''")
        _backfill_cars(db)

    user_columns = {row["name"] for row in db.execute("PRAGMA table_info(users)")}
    if "active" not in user_columns:
        db.execute("ALTER TABLE users ADD COLUMN active INTEGER NOT NULL DEFAULT 1")

    booking_columns = {row["name"] for row in db.execute("PRAGMA table_info(bookings)")}
    if "paid_amount" not in booking_columns:
        db.execute("ALTER TABLE bookings ADD COLUMN paid_amount REAL NOT NULL DEFAULT 0")
        db.execute("ALTER TABLE bookings ADD COLUMN paid_method TEXT NOT NULL DEFAULT ''")
        db.execute("ALTER TABLE bookings ADD COLUMN paid_at TEXT NOT NULL DEFAULT ''")


def _backfill_cars(db):
    """Fill the new display columns for a fleet created before the change."""
    rows = db.execute("SELECT id FROM cars ORDER BY id").fetchall()
    for row, seed in zip(rows, SEED_CARS):
        db.execute(
            "UPDATE cars SET capacity = ?, price = ?, week = ?, specs = ? WHERE id = ?",
            (seed[4], seed[5], seed[6], seed[7], row["id"]),
        )


def _seed_cars(db):
    if db.execute("SELECT 1 FROM cars LIMIT 1").fetchone():
        return
    db.executemany(
        "INSERT INTO cars (name, type, description, image, capacity, price, week, specs)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        SEED_CARS,
    )


def _seed_admin(db, password=None, production=False, ephemeral=False):
    if db.execute("SELECT 1 FROM users WHERE is_admin = 1 LIMIT 1").fetchone():
        return

    email = os.environ.get("TT_ADMIN_EMAIL", "tomsafaris@gmail.com").strip().lower()
    provided = password or os.environ.get("TT_ADMIN_PASSWORD")
    if production and not provided:
        if ephemeral:
            print(
                "\n  No admin account created: TT_ADMIN_PASSWORD is not set and the "
                "database is ephemeral (serverless). Set TT_ADMIN_PASSWORD to enable "
                "admin login; the public site will still work.\n",
                file=sys.stderr,
                flush=True,
            )
            return None
        raise RuntimeError(
            "No admin account exists and TT_ADMIN_PASSWORD is not set. "
            "In production, set TT_ADMIN_PASSWORD (and optionally TT_ADMIN_EMAIL) "
            "before the first start."
        )

    generated = not provided
    password = provided or secrets.token_urlsafe(12)

    if db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
        print(
            f"\n  Could not create the admin account: {email} is already registered.\n"
            "  Set TT_ADMIN_EMAIL to another address or create the admin manually.\n",
            file=sys.stderr,
            flush=True,
        )
        return None

    db.execute(
        "INSERT INTO users (first_name, last_name, email, phone, password_hash, is_admin)"
        " VALUES (?, ?, ?, ?, ?, 1)",
        (
            "Thomas",
            "Transfer",
            email,
            "0788652120",
            generate_password_hash(password),
        ),
    )

    if generated and not production:
        print(
            "\n"
            "  Admin account created (development bootstrap).\n"
            f"    email:    {email}\n"
            f"    password: {password}\n"
            "  Set TT_ADMIN_PASSWORD before the first run in production. "
            "This password is shown only once.\n",
            file=sys.stderr,
            flush=True,
        )
    return password
