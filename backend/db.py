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
SEED_CARS = [
    (
        "Toyota Corolla Hybrid",
        "Economy sedan",
        "Economical and comfortable for city rides and airport trips.",
        "/assets/images/cars/01-toyota-corolla-hybrid.jpg",
    ),
    (
        "Toyota Land Cruiser",
        "Large SUV",
        "Strong and spacious for long distance and rough roads.",
        "/assets/images/cars/02-toyota-land-cruiser.jpg",
    ),
    (
        "Toyota RAV4",
        "Compact SUV",
        "Modern, smooth and good for small families.",
        "/assets/images/cars/03-toyota-rav4.jpg",
    ),
    (
        "Mercedes-Benz G-Class",
        "Luxury SUV",
        "A premium ride for special occasions and VIP guests.",
        "/assets/images/cars/04-mercedes-benz-g-class.jpg",
    ),
    (
        "Volkswagen Transporter",
        "Van",
        "Roomy and comfortable for groups with luggage.",
        "/assets/images/cars/05-volkswagen-transporter.jpg",
    ),
    (
        "Mercedes-AMG GLE Coupe",
        "Luxury SUV",
        "A fast, stylish ride for executive travel.",
        "/assets/images/cars/06-mercedes-amg-gle-coupe.jpg",
    ),
    (
        "Toyota Land Cruiser Prado, black",
        "Mid-size SUV",
        "A reliable all-round vehicle for family and business trips.",
        "/assets/images/cars/07-toyota-land-cruiser-prado-black.jpg",
    ),
    (
        "Toyota Land Cruiser Prado, black (rear view)",
        "Mid-size SUV",
        "Large luggage space and comfortable seating.",
        "/assets/images/cars/08-toyota-land-cruiser-prado-rear.jpg",
    ),
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
    """Create missing tables and seed the fleet plus the first admin account."""
    db = get_db()
    db.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    _seed_cars(db)
    _seed_admin(db, admin_password, production=production, ephemeral=ephemeral)
    db.commit()


def _seed_cars(db):
    if db.execute("SELECT 1 FROM cars LIMIT 1").fetchone():
        return
    db.executemany(
        "INSERT INTO cars (name, type, description, image) VALUES (?, ?, ?, ?)",
        SEED_CARS,
    )


def _seed_admin(db, password=None, production=False, ephemeral=False):
    if db.execute("SELECT 1 FROM users WHERE is_admin = 1 LIMIT 1").fetchone():
        return

    email = os.environ.get("TT_ADMIN_EMAIL", "admin@thomastransfer.com").strip().lower()
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
            "0784659514",
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
