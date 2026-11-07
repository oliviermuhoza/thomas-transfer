"""Thomas Transfer API and static file server.

Run with `python -m backend.app` (development) or point a WSGI server at
`backend.app:app`. The API paths and response shapes match what the scripts in
`web/js/` expect; see README.md for the endpoint table.
"""

import os
import re
import secrets
import tempfile
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse

from flask import (
    Flask,
    current_app,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
)
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash

try:
    from .db import close_db, get_db, init_db
    from .pages import pages
except ImportError:  # running directly as `python backend/app.py`
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from backend.db import close_db, get_db, init_db
    from backend.pages import pages

PACKAGE_DIR = Path(__file__).resolve().parent
WEB_DIR = PACKAGE_DIR.parent / "web"  # static site root

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9\s().-]{6,28}[0-9]$")
CAR_STATUSES = {"available", "maintenance"}
BOOKING_STATUSES = {"pending", "confirmed", "completed", "cancelled"}
BOOKING_TRANSITIONS = {
    "pending": {"confirmed", "cancelled"},
    "confirmed": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}
# Seeded fleet order/capacities (no schema column); used for booking validation.
CAR_CAPACITIES = {1: 4, 2: 7, 3: 5, 4: 5, 5: 8, 6: 5, 7: 7, 8: 7}


def create_app(database=None, secret_key=None, admin_password=None, production=None):
    production = (
        os.environ.get("TT_ENV", "").strip().lower() == "production"
        if production is None
        else bool(production)
    )
    # Vercel's filesystem is read-only except for /tmp. Resolve to a writable
    # database path instead of crashing the function at import time.
    database = _resolve_database(database or os.environ.get("TT_DATABASE"))
    ephemeral = _truthy_env("VERCEL") or _is_ephemeral_db(database)
    data_dir = PACKAGE_DIR / "data" if database == ":memory:" else Path(database).parent

    # Vercel serves the app over HTTPS, so secure cookies are the correct default.
    cookie_secure = _truthy_env("TT_COOKIE_SECURE") or _truthy_env("VERCEL")
    if production and not cookie_secure:
        raise RuntimeError(
            "TT_COOKIE_SECURE=1 is required in production (HTTPS). "
            "Set TT_ENV=production only when served behind HTTPS."
        )

    app = Flask(__name__, static_folder=None)
    rate_limit_backend = os.environ.get("TT_RATE_LIMIT_BACKEND", "memory").strip().lower()
    app.config.update(
        PRODUCTION=production,
        DATABASE=database,
        SECRET_KEY=secret_key
        or _load_secret_key(data_dir, production=production, allow_ephemeral=ephemeral),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=cookie_secure,
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
        MAX_CONTENT_LENGTH=64 * 1024,
        RATE_LIMITS=defaultdict(deque),
        RATE_LIMIT_BACKEND=rate_limit_backend,
        RATE_LIMIT_REDIS=None,
    )
    if _truthy_env("TT_TRUST_PROXY_HEADERS"):
        hops = int(os.environ.get("TT_TRUSTED_PROXY_HOPS", "1") or "1")
        app.wsgi_app = ProxyFix(
            app.wsgi_app, x_for=hops, x_proto=hops, x_host=hops, x_port=hops
        )
        app.config["TRUST_PROXY_HEADERS"] = True
    if rate_limit_backend == "redis":
        redis_url = os.environ.get("TT_REDIS_URL")
        if not redis_url:
            raise RuntimeError("TT_REDIS_URL is required when TT_RATE_LIMIT_BACKEND=redis.")
        try:
            import redis  # optional dependency
        except ImportError as exc:
            raise RuntimeError(
                "TT_RATE_LIMIT_BACKEND=redis requires the 'redis' package."
            ) from exc
        client = redis.Redis.from_url(redis_url)
        client.ping()
        app.config["RATE_LIMIT_REDIS"] = client
    elif production:
        app.logger.warning(
            "Using in-memory rate limiting in production; set TT_RATE_LIMIT_BACKEND=redis "
            "and TT_REDIS_URL for shared limits across workers, or enforce limits at the edge/WAF."
        )
    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db(admin_password, production=production, ephemeral=ephemeral)

    register_routes(app)
    app.register_blueprint(pages)

    @app.context_processor
    def inject_current_user():
        try:
            user = current_user()
        except Exception:
            return {"current_user": None}
        return {"current_user": user_json(user) if user else None}

    @app.before_request
    def protect_api_requests():
        if not request.path.startswith("/api/"):
            return None
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            origin_error = _check_same_origin()
            if origin_error:
                return origin_error
            if not request.is_json:
                return error("Send a JSON request.", 415)
            expected = session.get("csrf_token")
            provided = request.headers.get("X-CSRF-Token", "")
            if not expected or not provided or not secrets.compare_digest(str(expected), str(provided)):
                return _csrf_error()
        return None

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(err):
        if request.path.startswith("/api/"):
            return error("Request is too large.", 413)
        return err

    @app.errorhandler(404)
    def not_found(err):
        if request.path.startswith("/api/"):
            return error("Not found.", 404)
        return (
            render_template(
                "errors/404.html",
                page="404",
                page_title="Page not found — Thomas Transfer",
                page_description="The page you asked for does not exist.",
            ),
            404,
        )

    @app.errorhandler(HTTPException)
    def http_errors(err):
        if request.path.startswith("/api/"):
            return error(err.description or "Request failed.", err.code or 400)
        return err

    @app.errorhandler(Exception)
    def unexpected_errors(err):
        app.logger.exception("Unhandled error")
        if request.path.startswith("/api/"):
            return error("Something went wrong. Please try again.", 500)
        return (
            "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<title>Something went wrong — Thomas Transfer</title></head>"
            "<body><h1>Something went wrong</h1><p>Please try again.</p></body></html>",
            500,
            {"Content-Type": "text/html; charset=utf-8"},
        )

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        return response

    return app


def _truthy_env(name):
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _probe_writable(directory):
    """Return True when files can be created in ``directory``."""
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".tt-write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def _is_ephemeral_db(database):
    if database == ":memory:":
        return True
    try:
        return Path(database).resolve().is_relative_to(
            Path(tempfile.gettempdir()).resolve()
        )
    except (OSError, ValueError):
        return False


def _resolve_database(requested):
    """Pick the first writable database path.

    Serverless platforms (Vercel) mount the project read-only and only allow
    writes under ``/tmp``. A misconfigured ``TT_DATABASE`` must not take the
    whole function down at import time.
    """
    if requested == ":memory:":
        return requested
    candidates = []
    if requested:
        candidates.append(Path(requested))
    candidates.append(PACKAGE_DIR / "data" / "thomas.db")
    candidates.append(Path(tempfile.gettempdir()) / "thomas-transfer-data" / "thomas.db")
    for candidate in candidates:
        if _probe_writable(candidate.parent):
            return str(candidate)
    return ":memory:"


def _load_secret_key(data_dir, production=False, allow_ephemeral=False):
    """Use SECRET_KEY when given, otherwise keep a generated key across restarts."""
    key = os.environ.get("SECRET_KEY")
    if key:
        return key
    if production and not allow_ephemeral:
        raise RuntimeError("SECRET_KEY must be set in production.")
    path = data_dir / "secret_key"
    try:
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    key = secrets.token_hex(32)
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(key, encoding="utf-8")
    except OSError:
        pass  # read-only filesystem: ephemeral key is fine
    return key


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def error(message, status):
    return jsonify({"error": message}), status


def body():
    return request.get_json(silent=True) or {}


def _ensure_csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
        session.modified = True
    return token


def _csrf_error():
    return error("Invalid or missing CSRF token.", 403)


def _client_ip():
    # request.remote_addr is normalized by ProxyFix when TT_TRUST_PROXY_HEADERS is set.
    return request.remote_addr or "unknown"


def _rate_limited_memory(bucket, limit, window_seconds):
    store = current_app.config.setdefault("RATE_LIMITS", defaultdict(deque))
    key = (bucket, _client_ip())
    now = time.monotonic()
    hits = store[key]
    cutoff = now - window_seconds
    while hits and hits[0] <= cutoff:
        hits.popleft()
    if len(hits) >= limit:
        return True
    hits.append(now)
    return False


def _rate_limited_redis(bucket, limit, window_seconds):
    client = current_app.config.get("RATE_LIMIT_REDIS")
    if client is None:
        return _rate_limited_memory(bucket, limit, window_seconds)
    key = f"tt:rl:{bucket}:{_client_ip()}"
    try:
        # Fixed window counter; simple and dependency-free on Redis side.
        current = client.incr(key)
        if current == 1:
            client.expire(key, window_seconds)
        return current > limit
    except Exception:
        current_app.logger.warning("Redis rate limiter unavailable; allowing request")
        return False


def _rate_limited(bucket, limit, window_seconds):
    backend = current_app.config.get("RATE_LIMIT_BACKEND", "memory")
    if backend == "redis":
        return _rate_limited_redis(bucket, limit, window_seconds)
    return _rate_limited_memory(bucket, limit, window_seconds)


def _check_same_origin():
    # Defense-in-depth for cookie-authenticated API writes. Browsers send Origin on
    # cross-site requests; same-origin test/CLI clients may omit it.
    origin = request.headers.get("Origin")
    if origin:
        expected = {request.host_url.rstrip("/"), f"{request.scheme}://{request.host}"}
        return None if origin.rstrip("/") in expected else error("Invalid request origin.", 403)
    referer = request.headers.get("Referer")
    if referer:
        ref = urlparse(referer)
        if ref.netloc and ref.netloc != request.host:
            return error("Invalid request origin.", 403)
    return None


def text_value(data, key, max_length):
    value = data.get(key)
    return "" if value is None else str(value).strip()[:max_length]


def valid_phone(phone):
    phone = (phone or "").strip()
    return not phone or bool(PHONE_RE.match(phone))


def car_capacity(car):
    return CAR_CAPACITIES.get(car["id"], 60)


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def user_json(user):
    return {
        "id": user["id"],
        "name": f"{user['first_name']} {user['last_name']}".strip(),
        "email": user["email"],
        "phone": user["phone"],
        "admin": bool(user["is_admin"]),
    }


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            return error("Please login first.", 401)
        g.user = user
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            return error("Please login first.", 401)
        if not user["is_admin"]:
            return error("This page is for the admin only.", 403)
        g.user = user
        return view(*args, **kwargs)

    return wrapped


def parse_trip_at(raw):
    raw = str(raw or "").strip()
    try:
        moment = datetime.fromisoformat(raw)
    except ValueError:
        return None, "Please choose a valid date and time."
    if moment.tzinfo is not None:
        return None, "Please choose a local date and time."
    if moment < datetime.now() - timedelta(minutes=5):
        return None, "Please choose a date and time in the future."
    return moment.isoformat(timespec="minutes"), None


def parse_rating(raw):
    if isinstance(raw, int):
        value = raw
    else:
        match = re.match(r"\s*([1-5])", str(raw or ""))
        value = int(match.group(1)) if match else None
    return value if value in (1, 2, 3, 4, 5) else None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def register_routes(app):
    # ---------- static assets ----------
    # Pages are rendered by the `pages` blueprint in backend/pages.py.

    @app.get("/index.html")
    def index_html():
        return redirect("/", code=302)

    @app.get("/css/<path:filename>")
    def css(filename):
        return send_from_directory(WEB_DIR / "css", filename)

    @app.get("/js/<path:filename>")
    def js(filename):
        return send_from_directory(WEB_DIR / "js", filename)

    @app.get("/assets/<path:filename>")
    def assets(filename):
        return send_from_directory(WEB_DIR / "assets", filename)

    # ---------- accounts ----------

    @app.get("/api/csrf")
    def csrf():
        return jsonify({"csrf_token": _ensure_csrf_token()})

    @app.get("/api/me")
    def me():
        csrf_token = _ensure_csrf_token()
        try:
            user = current_user()
        except Exception:
            app.logger.exception("Failed to load current user")
            return jsonify({"user": None, "csrf_token": csrf_token})
        return jsonify({"user": user_json(user) if user else None, "csrf_token": csrf_token})

    @app.post("/api/register")
    def register():
        if _rate_limited("register", limit=10, window_seconds=3600):
            return error("Too many attempts. Please try again later.", 429)
        data = body()
        first_name = text_value(data, "first_name", 50)
        last_name = text_value(data, "last_name", 50)
        email = text_value(data, "email", 150).lower()
        phone = text_value(data, "phone", 30)
        password = str(data.get("password") or "")

        if not first_name or not last_name or not email or not password:
            return error("Please fill in all the fields.", 400)
        if not EMAIL_RE.match(email):
            return error("Please enter a valid email address.", 400)
        if not valid_phone(phone):
            return error("Please enter a valid phone number.", 400)
        if len(password) < 8:
            return error("Use at least 8 characters for the password.", 400)

        db = get_db()
        exists = db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone()
        if exists:
            return error("Could not create the account with that email.", 409)

        cursor = db.execute(
            "INSERT INTO users (first_name, last_name, email, phone, password_hash)"
            " VALUES (?, ?, ?, ?, ?)",
            (first_name, last_name, email, phone, generate_password_hash(password)),
        )
        db.commit()

        user = db.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
        session.clear()
        session.permanent = True
        session["user_id"] = user["id"]
        session["csrf_token"] = secrets.token_urlsafe(32)
        return jsonify({"user": user_json(user), "csrf_token": session["csrf_token"]}), 201

    @app.post("/api/login")
    def login():
        if _rate_limited("login", limit=15, window_seconds=60):
            return error("Too many attempts. Please try again later.", 429)
        data = body()
        email = text_value(data, "email", 150).lower()
        password = str(data.get("password") or "")
        if not email or not password:
            return error("Please enter your email and password.", 400)

        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            return error("Wrong email or password.", 401)

        session.clear()
        session.permanent = True
        session["user_id"] = user["id"]
        session["csrf_token"] = secrets.token_urlsafe(32)
        return jsonify({"user": user_json(user), "csrf_token": session["csrf_token"]})

    @app.post("/api/logout")
    def logout():
        session.clear()
        session["csrf_token"] = secrets.token_urlsafe(32)
        return jsonify({"ok": True, "csrf_token": session["csrf_token"]})

    # ---------- fleet ----------

    @app.get("/api/cars")
    def list_cars():
        query = "SELECT id, name, type, description, image, status FROM cars"
        if request.args.get("available") in ("1", "true", "yes"):
            query += " WHERE status = 'available'"
        query += " ORDER BY id"
        return jsonify([dict(row) for row in get_db().execute(query)])

    @app.post("/api/cars/<int:car_id>/status")
    @admin_required
    def car_status(car_id):
        status = str(body().get("status") or "")
        if status not in CAR_STATUSES:
            return error("Unknown car status.", 400)

        db = get_db()
        car = db.execute("SELECT * FROM cars WHERE id = ?", (car_id,)).fetchone()
        if car is None:
            return error("This car does not exist.", 404)
        if car["status"] == "booked":
            return error("This car has an active booking. Cancel or complete it first.", 409)

        db.execute("UPDATE cars SET status = ? WHERE id = ?", (status, car_id))
        db.commit()
        return jsonify({"ok": True, "status": status})

    # ---------- bookings ----------

    @app.get("/api/bookings")
    @login_required
    def list_bookings():
        db = get_db()
        query = """
            SELECT b.id, b.user_id, b.pickup, b.dropoff, b.trip_at, b.passengers,
                   b.notes, b.status, b.created_at,
                   c.name AS car_name,
                   u.first_name || ' ' || u.last_name AS customer,
                   u.phone, u.email
              FROM bookings b
              JOIN cars c  ON c.id = b.car_id
              JOIN users u ON u.id = b.user_id
        """
        if g.user["is_admin"]:
            rows = db.execute(query + " ORDER BY b.id DESC").fetchall()
        else:
            rows = db.execute(
                query + " WHERE b.user_id = ? ORDER BY b.id DESC", (g.user["id"],)
            ).fetchall()
        return jsonify([dict(row) for row in rows])

    @app.post("/api/bookings")
    @login_required
    def create_booking():
        data = body()
        pickup = text_value(data, "pickup", 150)
        dropoff = text_value(data, "dropoff", 150)
        notes = text_value(data, "notes", 500)

        try:
            car_id = int(data.get("car_id"))
        except (TypeError, ValueError):
            return error("Please choose a car.", 400)
        try:
            passengers = int(data.get("passengers", 1))
        except (TypeError, ValueError):
            return error("Passengers must be a number.", 400)

        if not pickup or not dropoff:
            return error("Please fill in all the fields.", 400)
        if pickup.casefold() == dropoff.casefold():
            return error("Pick-up and drop-off places must be different.", 400)
        if not 1 <= passengers <= 60:
            return error("Passengers must be between 1 and 60.", 400)

        trip_at, problem = parse_trip_at(data.get("trip_at"))
        if problem:
            return error(problem, 400)

        db = get_db()
        car = db.execute("SELECT * FROM cars WHERE id = ?", (car_id,)).fetchone()
        if car is None:
            return error("This car does not exist.", 404)
        if car["status"] != "available":
            return error("This car is not available. Please choose another car.", 409)
        capacity = car_capacity(car)
        if passengers > capacity:
            return error(f"This car can take up to {capacity} passengers.", 400)

        taken = db.execute(
            "UPDATE cars SET status = 'booked' WHERE id = ? AND status = 'available'",
            (car_id,),
        )
        if taken.rowcount == 0:
            db.rollback()
            return error("This car is not available. Please choose another car.", 409)

        cursor = db.execute(
            "INSERT INTO bookings"
            " (user_id, car_id, pickup, dropoff, trip_at, passengers, notes)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (g.user["id"], car_id, pickup, dropoff, trip_at, passengers, notes),
        )
        db.commit()
        return jsonify({"ok": True, "id": cursor.lastrowid}), 201

    @app.post("/api/bookings/<int:booking_id>/status")
    @login_required
    def booking_status(booking_id):
        new_status = str(body().get("status") or "")
        if new_status not in BOOKING_STATUSES:
            return error("Unknown booking status.", 400)

        db = get_db()
        booking = db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
        if booking is None:
            return error("This booking does not exist.", 404)

        if g.user["is_admin"]:
            if new_status not in BOOKING_TRANSITIONS.get(booking["status"], set()):
                return error("That status change is not allowed.", 400)
        else:
            if booking["user_id"] != g.user["id"]:
                return error("You can only change your own bookings.", 403)
            if new_status != "cancelled" or booking["status"] not in ("pending", "confirmed"):
                return error("You can only cancel your booking.", 400)

        db.execute("UPDATE bookings SET status = ? WHERE id = ?", (new_status, booking_id))
        if new_status in ("cancelled", "completed"):
            db.execute(
                "UPDATE cars SET status = 'available' WHERE id = ? AND status = 'booked'",
                (booking["car_id"],),
            )
        db.commit()
        return jsonify({"ok": True, "status": new_status})

    # ---------- admin report ----------

    @app.get("/api/report")
    @admin_required
    def report():
        db = get_db()
        car_counts = db.execute(
            "SELECT COUNT(*) AS total,"
            " SUM(status = 'available')   AS available,"
            " SUM(status = 'booked')      AS booked,"
            " SUM(status = 'maintenance') AS maintenance"
            " FROM cars"
        ).fetchone()
        booking_counts = db.execute(
            "SELECT COUNT(*) AS total,"
            " SUM(status = 'pending')   AS pending,"
            " SUM(status = 'confirmed') AS confirmed,"
            " SUM(status = 'completed') AS completed,"
            " SUM(status = 'cancelled') AS cancelled"
            " FROM bookings"
        ).fetchone()
        comment_counts = db.execute(
            "SELECT COUNT(*) AS count, AVG(rating) AS average FROM comments"
        ).fetchone()
        per_car = db.execute(
            "SELECT c.name, c.type, COUNT(b.id) AS total,"
            " SUM(CASE WHEN b.status = 'completed' THEN 1 ELSE 0 END) AS completed"
            " FROM cars c LEFT JOIN bookings b ON b.car_id = c.id"
            " GROUP BY c.id ORDER BY c.id"
        ).fetchall()
        accounts = db.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        messages = db.execute("SELECT COUNT(*) AS n FROM messages").fetchone()["n"]
        average = (
            round(comment_counts["average"], 1)
            if comment_counts["average"] is not None
            else None
        )

        return jsonify(
            {
                "cars": {
                    "total": car_counts["total"],
                    "available": car_counts["available"] or 0,
                    "booked": car_counts["booked"] or 0,
                    "maintenance": car_counts["maintenance"] or 0,
                },
                "bookings": {
                    "total": booking_counts["total"] or 0,
                    "pending": booking_counts["pending"] or 0,
                    "confirmed": booking_counts["confirmed"] or 0,
                    "completed": booking_counts["completed"] or 0,
                    "cancelled": booking_counts["cancelled"] or 0,
                },
                "accounts": accounts,
                "comments": {
                    "count": comment_counts["count"],
                    "average": average,
                },
                "messages": messages,
                "per_car": [
                    {
                        "name": row["name"],
                        "type": row["type"],
                        "total": row["total"],
                        "completed": row["completed"] or 0,
                    }
                    for row in per_car
                ],
            }
        )

    # ---------- comments and messages ----------

    @app.post("/api/comment")
    def comment():
        if _rate_limited("public_write", limit=20, window_seconds=600):
            return error("Too many attempts. Please try again later.", 429)
        data = body()
        name = text_value(data, "name", 100)
        text = text_value(data, "text", 2000)
        rating = parse_rating(data.get("rating"))

        if not name or not text:
            return error("Please write your name and your comment.", 400)
        if rating is None:
            return error("Please choose a rating.", 400)

        try:
            user = current_user()
        except Exception:
            user = None
        db = get_db()
        db.execute(
            "INSERT INTO comments (user_id, name, rating, text) VALUES (?, ?, ?, ?)",
            (user["id"] if user else None, name, rating, text),
        )
        db.commit()
        return jsonify({"ok": True}), 201

    @app.post("/api/contact")
    def contact():
        if _rate_limited("public_write", limit=20, window_seconds=600):
            return error("Too many attempts. Please try again later.", 429)
        data = body()
        name = text_value(data, "name", 100)
        email = text_value(data, "email", 150).lower()
        phone = text_value(data, "phone", 30)
        service = text_value(data, "service", 100)
        message = text_value(data, "message", 2000)

        if not name or not email or not message:
            return error("Please fill in your name, email and message.", 400)
        if not EMAIL_RE.match(email):
            return error("Please enter a valid email address.", 400)
        if not valid_phone(phone):
            return error("Please enter a valid phone number.", 400)

        db = get_db()
        db.execute(
            "INSERT INTO messages (name, email, phone, service, message)"
            " VALUES (?, ?, ?, ?, ?)",
            (name, email, phone, service, message),
        )
        db.commit()
        return jsonify({"ok": True}), 201


app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.environ.get("TT_HOST", "127.0.0.1"),
        port=int(os.environ.get("TT_PORT", "5000")),
        debug=os.environ.get("TT_DEBUG") == "1",
    )
