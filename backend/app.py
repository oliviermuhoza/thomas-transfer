"""TOM Safaris API and static file server.

Run with `python -m backend.app` (development) or point a WSGI server at
`backend.app:app`. The API paths and response shapes match what the scripts in
`web/js/` expect; see README.md for the endpoint table.
"""

import hashlib
import os
import re
import secrets
import tempfile
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path
from urllib.parse import quote, urlparse

from flask import (
    Flask,
    Response,
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
    from .mailer import configured as mail_configured, send_email
    from .pages import format_price, pages
except ImportError:  # running directly, or loaded as a top-level module by Vercel
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from backend.db import close_db, get_db, init_db
        from backend.mailer import configured as mail_configured, send_email
        from backend.pages import format_price, pages
    except ImportError:  # deployment root is backend/ itself
        from db import close_db, get_db, init_db
        from mailer import configured as mail_configured, send_email
        from pages import format_price, pages

PACKAGE_DIR = Path(__file__).resolve().parent
WEB_DIR = PACKAGE_DIR.parent / "web"  # static site root
PROJECT_DIR = PACKAGE_DIR.parent


def load_env_file(path=None):
    """Fill os.environ from a KEY=VALUE file, if the file exists.

    Deliberately tiny and dependency-free: no python-dotenv, no .env parser
    features. Existing environment variables always win, so the platform (or a
    shell export) can override anything in the file. Lines starting with # and
    blank lines are ignored; surrounding single or double quotes are stripped.

    Set TT_NO_ENV_FILE=1 to ignore the file completely. The test suite does
    this so a developer's local .env can never change test behaviour.
    """
    if os.environ.get("TT_NO_ENV_FILE"):
        return False
    path = Path(path) if path else PROJECT_DIR / ".env"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) > 1 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value
    return True


load_env_file()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9\s().-]{6,28}[0-9]$")
CAR_STATUSES = {"available", "maintenance"}
BOOKING_STATUSES = {"pending", "confirmed", "completed", "cancelled"}
FARE_CURRENCIES = {"RWF", "USD"}
FARE_KEY_RE = re.compile(r"^[a-z][a-z0-9_-]{1,29}$")
BOOKING_TRANSITIONS = {
    "pending": {"confirmed", "cancelled"},
    "confirmed": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}
# Editable car fields and their text limits (capacity is validated separately).
CAR_TEXT_FIELDS = {
    "name": 100,
    "type": 60,
    "description": 300,
    "image": 300,
    "price": 40,
    "week": 80,
    "specs": 500,
}


def create_app(
    database=None,
    secret_key=None,
    admin_password=None,
    production=None,
    admin_email=None,
    db_driver=None,
    auto_init=True,
):
    production = (
        os.environ.get("TT_ENV", "").strip().lower() == "production"
        if production is None
        else bool(production)
    )
    # Turso/libSQL is remote, so the file-path probing below does not apply.
    # TURSO_DATABASE_URL is injected by the Vercel Turso integration.
    turso_url = os.environ.get("TURSO_DATABASE_URL", "").strip()
    db_driver = db_driver or os.environ.get("TT_DB_DRIVER", "").strip().lower() or None
    if turso_url:
        if not os.environ.get("TURSO_AUTH_TOKEN", "").strip():
            raise RuntimeError(
                "TURSO_AUTH_TOKEN is required when TURSO_DATABASE_URL is set."
            )
        database = turso_url
        db_driver = "libsql"
        ephemeral = False
        data_dir = Path(tempfile.gettempdir()) / "thomas-transfer-data"
    else:
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

    # A live deployment must not boot on a throwaway database: it would look
    # healthy while losing every booking on the next deploy or cold start.
    allow_ephemeral = _truthy_env("TT_ALLOW_EPHEMERAL_DB")
    vercel_env = os.environ.get("VERCEL_ENV", "").strip().lower()
    live = production or (_truthy_env("VERCEL") and vercel_env == "production")
    if live and ephemeral and not allow_ephemeral:
        raise RuntimeError(
            "No persistent database: the app resolved to an ephemeral location "
            f"({database}). Set TURSO_DATABASE_URL and TURSO_AUTH_TOKEN, or point "
            "TT_DATABASE at persistent storage. Set TT_ALLOW_EPHEMERAL_DB=1 only "
            "for a disposable demo."
        )

    app = Flask(__name__, static_folder=None)
    rate_limit_backend = os.environ.get("TT_RATE_LIMIT_BACKEND", "memory").strip().lower()
    app.config.update(
        PRODUCTION=production,
        DATABASE=database,
        DB_DRIVER=db_driver,
        DB_AUTH_TOKEN=os.environ.get("TURSO_AUTH_TOKEN", "").strip(),
        EPHEMERAL_DB=ephemeral,
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

    if turso_url:
        app.logger.info(
            "Database backend: libsql (%s)", urlparse(database).hostname or database
        )
    else:
        app.logger.info("Database backend: sqlite (%s)", database)

    if ephemeral and (production or _truthy_env("VERCEL")):
        app.logger.warning(
            "The database resolves to an ephemeral path; bookings and admin "
            "edits are lost on the next restart. Set TURSO_DATABASE_URL and "
            "TURSO_AUTH_TOKEN for persistent storage."
        )

    if auto_init:
        if not live or allow_ephemeral:
            with app.app_context():
                init_db(
                    admin_password,
                    production=production,
                    ephemeral=ephemeral,
                    admin_email=admin_email,
                )
        else:
            # Live deployments leave schema and seed data alone. Applying them
            # from every cold start is unnecessary and turns a config mistake
            # into unexplained data loss; run `python -m backend.initdb` once.
            app.logger.info(
                "Automatic schema/seed disabled for this deployment; "
                "run `python -m backend.initdb` after schema changes."
            )
            with app.app_context():
                try:
                    get_db().execute("SELECT 1 FROM users LIMIT 1").fetchone()
                except Exception as exc:
                    raise RuntimeError(
                        "The database has no schema (or is unreachable). Run "
                        "`python -m backend.initdb` once against it, then redeploy."
                    ) from exc

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
                page_title="Page not found — TOM Safaris",
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
            "<title>Something went wrong — TOM Safaris</title></head>"
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
    return car["capacity"]


def car_json(row):
    """Serialize a cars row; specs is stored newline-separated, returned as list."""
    car = dict(row)
    car["specs"] = [line for line in (car["specs"] or "").split("\n") if line]
    return car


def fare_json(row):
    fare = dict(row)
    fare["active"] = bool(fare["active"])
    fare["price"] = format_price(fare["amount"], fare["currency"])
    return fare


def _fare_payload(data, partial=False):
    """Validate a fare create/update body; returns (values, error_message)."""
    values = {}
    if "key" in data or not partial:
        key = text_value(data, "key", 30).lower()
        if not FARE_KEY_RE.match(key):
            return None, "The fare code must be 2-30 lowercase letters, digits, - or _."
        values["key"] = key
    for field, maximum in (("tag", 60), ("name", 100), ("note", 60), ("flw_link", 300)):
        if field in data or not partial:
            values[field] = text_value(data, field, maximum)
    if "name" in values and not values["name"]:
        return None, "Please give the fare a name."
    if not partial and "name" not in values:
        return None, "Please give the fare a name."
    if "amount" in data or not partial:
        try:
            amount = round(float(data.get("amount")), 2)
        except (TypeError, ValueError):
            return None, "Amount must be a number."
        if not 0 < amount <= 100000000:
            return None, "Amount must be greater than zero."
        values["amount"] = amount
    if "currency" in data:
        currency = text_value(data, "currency", 10).upper()
        if currency not in FARE_CURRENCIES:
            return None, "Currency must be RWF or USD."
        values["currency"] = currency
    elif not partial:
        values["currency"] = "RWF"
    if "active" in data:
        values["active"] = int(bool(data["active"]))
    link = values.get("flw_link")
    if link is not None and link and not link.startswith("https://"):
        return None, "The payment link must start with https://."
    return values, None


def _car_specs_value(raw):
    """Normalize free-text specs into one non-empty line per spec."""
    lines = [line.strip() for line in str(raw or "").replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line)[:500]


def _csv_response(filename, header, rows):
    """Build a downloadable CSV response (BOM so Excel reads UTF-8 correctly)."""

    def esc(value):
        value = "" if value is None else str(value)
        if any(char in value for char in ('"', ",", "\n", "\r")):
            value = '"' + value.replace('"', '""') + '"'
        return value

    lines = [",".join(esc(cell) for cell in header)]
    lines += [",".join(esc(cell) for cell in row) for row in rows]
    return Response(
        ("\ufeff" + "\r\n".join(lines) + "\r\n").encode("utf-8"),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def parse_capacity(raw):
    try:
        capacity = int(raw)
    except (TypeError, ValueError):
        return None, "Passengers capacity must be a number."
    if not 1 <= capacity <= 60:
        return None, "Capacity must be between 1 and 60 passengers."
    return capacity, None


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is not None and not user["active"]:
        # Deactivated accounts are treated as signed out everywhere.
        return None
    if user is not None and session.get("token_version", 0) != user["token_version"]:
        # The password was reset elsewhere; this session is no longer valid.
        session.clear()
        return None
    return user


def user_json(user):
    name = f"{user['first_name']} {user['last_name']}".strip()
    parts = [part for part in name.split() if part]
    initials = (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()
    return {
        "id": user["id"],
        "name": name,
        "email": user["email"],
        "phone": user["phone"],
        "admin": bool(user["is_admin"]),
        "initials": initials or user["email"][:1].upper(),
    }


RESET_TOKEN_TTL_MINUTES = 30


def _reset_token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _send_password_reset_email(user, link):
    """Send the reset link; never raise into the request handler."""
    name = f"{user['first_name']} {user['last_name']}".strip() or "there"
    body = (
        f"Hello {name},\n\n"
        "Someone asked to reset the password for your TOM Safaris account.\n"
        f"Open this link within {RESET_TOKEN_TTL_MINUTES} minutes to choose a new password:\n\n"
        f"{link}\n\n"
        "If you did not ask for this, ignore this message; your password stays the same.\n"
    )
    if mail_configured():
        try:
            send_email(
                user["email"], "Reset your TOM Safaris password", body
            )
            return True
        except Exception as exc:
            current_app.logger.error("Password reset email failed: %s", exc)
            return False
    if current_app.config.get("PRODUCTION"):
        current_app.logger.error(
            "Password reset email not sent: set TT_SMTP_HOST (and TT_SMTP_FROM) "
            "in the environment."
        )
    else:
        current_app.logger.warning(
            "Password reset link for %s: %s", user["email"], link
        )
    return False


def _send_booking_confirmation_email(customer, booking, car_name):
    """Tell the customer their booking was confirmed; never raise."""
    name = f"{customer['first_name']} {customer['last_name']}".strip() or "there"
    when = str(booking["trip_at"]).replace("T", " ")
    label = "Tour" if booking["kind"] == "tour" else "Car"
    body = (
        f"Hello {name},\n\n"
        "Good news - your TOM Safaris booking is confirmed.\n\n"
        f"Booking #{booking['id']}\n"
        f"{label}: {car_name}\n"
        f"From: {booking['pickup']}\n"
        f"To: {booking['dropoff']}\n"
        f"Date and time: {when}\n"
        f"Passengers: {booking['passengers']}\n\n"
        "Your driver will meet you on time. If your plans change, reply to "
        "this email or message us on WhatsApp.\n"
    )
    if mail_configured():
        try:
            send_email(
                customer["email"],
                f"Booking #{booking['id']} confirmed — TOM Safaris",
                body,
            )
            return True
        except Exception as exc:
            current_app.logger.error("Booking confirmation email failed: %s", exc)
            return False
    if current_app.config.get("PRODUCTION"):
        current_app.logger.error(
            "Booking confirmation email not sent: set TT_SMTP_HOST (and TT_SMTP_FROM) "
            "in the environment."
        )
    else:
        current_app.logger.warning(
            "Booking #%s confirmed for %s (email not configured).",
            booking["id"],
            customer["email"],
        )
    return False


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


def parse_trip_at(raw, require_future=True):
    raw = str(raw or "").strip()
    try:
        moment = datetime.fromisoformat(raw)
    except ValueError:
        return None, "Please choose a valid date and time."
    if moment.tzinfo is not None:
        return None, "Please choose a local date and time."
    if require_future and moment < datetime.now() - timedelta(minutes=5):
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
        # Public self-registration is disabled: staff create every account
        # through POST /api/admin/users.
        return error(
            "Public registration is disabled."
            " Please contact our team to create an account.",
            403,
        )

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
        if not user["active"]:
            return error("This account has been deactivated. Please contact support.", 401)
        if not user["is_admin"]:
            return error("This login is for staff only.", 403)

        session.clear()
        session.permanent = True
        session["user_id"] = user["id"]
        session["token_version"] = user["token_version"]
        session["csrf_token"] = secrets.token_urlsafe(32)
        return jsonify({"user": user_json(user), "csrf_token": session["csrf_token"]})

    @app.post("/api/logout")
    def logout():
        session.clear()
        session["csrf_token"] = secrets.token_urlsafe(32)
        return jsonify({"ok": True, "csrf_token": session["csrf_token"]})

    # ---------- password reset ----------

    @app.post("/api/password/forgot")
    def forgot_password():
        if _rate_limited("password-forgot", limit=10, window_seconds=3600):
            return error("Too many requests. Please try again later.", 429)
        data = body()
        email = text_value(data, "email", 150).lower()
        if not email or not EMAIL_RE.match(email):
            return error("Please enter a valid email address.", 400)

        generic = "If that email is registered, a reset link is on its way."
        if _rate_limited(f"password-forgot:{email}", limit=3, window_seconds=3600):
            return jsonify({"ok": True, "message": generic})

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email = ? AND active = 1", (email,)
        ).fetchone()
        if user is not None:
            db.execute("DELETE FROM password_resets WHERE user_id = ?", (user["id"],))
            token = secrets.token_urlsafe(32)
            db.execute(
                "INSERT INTO password_resets (user_id, token_hash, expires_at)"
                " VALUES (?, ?, datetime('now', '+30 minutes'))",
                (user["id"], _reset_token_hash(token)),
            )
            db.commit()
            link = request.url_root.rstrip("/") + "/reset?token=" + quote(token)
            _send_password_reset_email(user, link)
        return jsonify({"ok": True, "message": generic})

    @app.post("/api/password/reset")
    def reset_password():
        if _rate_limited("password-reset", limit=15, window_seconds=900):
            return error("Too many attempts. Please try again later.", 429)
        data = body()
        token = str(data.get("token") or "").strip()
        password = str(data.get("password") or "")
        if len(password) < 8:
            return error("Use at least 8 characters for the password.", 400)
        if not token:
            return error("This reset link is invalid or has expired.", 400)

        db = get_db()
        row = db.execute(
            "SELECT pr.id, pr.user_id FROM password_resets pr"
            " JOIN users u ON u.id = pr.user_id"
            " WHERE pr.token_hash = ? AND pr.used_at IS NULL"
            " AND pr.expires_at > datetime('now') AND u.active = 1",
            (_reset_token_hash(token),),
        ).fetchone()
        if row is None:
            return error("This reset link is invalid or has expired.", 400)

        db.execute(
            "UPDATE users SET password_hash = ?, token_version = token_version + 1"
            " WHERE id = ?",
            (generate_password_hash(password), row["user_id"]),
        )
        db.execute(
            "UPDATE password_resets SET used_at = datetime('now') WHERE id = ?",
            (row["id"],),
        )
        db.execute(
            "DELETE FROM password_resets WHERE user_id = ? AND used_at IS NULL",
            (row["user_id"],),
        )
        db.commit()
        session.clear()
        session["csrf_token"] = secrets.token_urlsafe(32)
        return jsonify(
            {
                "ok": True,
                "message": "Your password has been updated. You can sign in now.",
                "csrf_token": session["csrf_token"],
            }
        )

    # ---------- fleet ----------

    @app.get("/api/cars")
    def list_cars():
        query = (
            "SELECT id, name, type, description, image, status,"
            " capacity, price, week, specs FROM cars"
        )
        if request.args.get("available") in ("1", "true", "yes"):
            query += " WHERE status = 'available'"
        query += " ORDER BY id"

        # Everything about a car now lives in the cars table; specs is stored
        # as newline-separated text and returned as a list of display lines.
        cars = []
        for row in get_db().execute(query):
            car = dict(row)
            car["specs"] = [line for line in car["specs"].split("\n") if line]
            cars.append(car)
        return jsonify(cars)

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
            SELECT b.id, b.user_id, b.car_id, b.kind, b.pickup, b.dropoff,
                   b.trip_at, b.passengers, b.notes, b.status,
                   b.paid_amount, b.paid_method, b.paid_at, b.created_at,
                   COALESCE(c.name, NULLIF(b.tour_name, ''), '') AS car_name,
                   TRIM(COALESCE(u.first_name, '') || ' ' || COALESCE(u.last_name, '')) AS account_customer,
                   u.phone AS account_phone,
                   u.email AS account_email,
                   b.customer_name, b.customer_email, b.customer_phone, b.tour_name
              FROM bookings b
              LEFT JOIN cars c  ON c.id = b.car_id
              LEFT JOIN users u ON u.id = b.user_id
        """
        if g.user["is_admin"]:
            rows = db.execute(query + " ORDER BY b.id DESC").fetchall()
        else:
            rows = db.execute(
                query + " WHERE b.user_id = ? ORDER BY b.id DESC", (g.user["id"],)
            ).fetchall()

        bookings = []
        for row in rows:
            booking = dict(row)
            booking["customer"] = (
                booking["customer_name"] or booking["account_customer"] or "Guest"
            )
            booking["phone"] = booking["customer_phone"] or booking["account_phone"] or ""
            booking["email"] = booking["customer_email"] or booking["account_email"] or ""
            for key in ("account_customer", "account_phone", "account_email"):
                booking.pop(key, None)
            bookings.append(booking)
        return jsonify(bookings)

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

        # An admin may book on behalf of a customer (phone or walk-in trips).
        user_id = g.user["id"]
        if g.user["is_admin"] and data.get("user_id") is not None:
            try:
                user_id = int(data.get("user_id"))
            except (TypeError, ValueError):
                return error("Choose a valid customer account.", 400)
            customer = db.execute(
                "SELECT id FROM users WHERE id = ? AND active = 1", (user_id,)
            ).fetchone()
            if customer is None:
                return error("This account does not exist.", 404)

        taken = db.execute(
            "UPDATE cars SET status = 'booked' WHERE id = ? AND status = 'available'",
            (car_id,),
        )
        if taken.rowcount == 0:
            db.rollback()
            return error("This car is not available. Please choose another car.", 409)

        cursor = db.execute(
            "INSERT INTO bookings"
            " (user_id, car_id, kind, pickup, dropoff, trip_at, passengers, notes)"
            " VALUES (?, ?, 'car', ?, ?, ?, ?, ?)",
            (user_id, car_id, pickup, dropoff, trip_at, passengers, notes),
        )
        db.commit()
        return jsonify({"ok": True, "id": cursor.lastrowid}), 201

    @app.post("/api/bookings/guest")
    def create_guest_booking():
        """Public car reservation or tour request; stored in bookings, not messages."""
        if _rate_limited("public_write", limit=20, window_seconds=600):
            return error("Too many attempts. Please try again later.", 429)

        data = body()
        kind = str(data.get("kind") or "car").strip().lower()
        if kind not in ("car", "tour"):
            return error("Please choose a booking type.", 400)

        name = text_value(data, "name", 100)
        email = text_value(data, "email", 150).lower()
        phone = text_value(data, "phone", 30)
        pickup = text_value(data, "pickup", 150)
        dropoff = text_value(data, "dropoff", 150)
        notes = text_value(data, "notes", 500)
        tour_name = text_value(data, "tour_name", 120)

        if not name or not email or not phone or not pickup:
            return error("Please fill in your name, email, phone and pick-up.", 400)
        if not EMAIL_RE.match(email):
            return error("Please enter a valid email address.", 400)
        if not valid_phone(phone):
            return error("Please enter a valid phone number.", 400)
        if kind == "tour" and not tour_name:
            return error("Please choose a tour package.", 400)
        if dropoff and pickup.casefold() == dropoff.casefold():
            return error("Pick-up and drop-off places must be different.", 400)

        try:
            passengers = int(data.get("passengers", 1))
        except (TypeError, ValueError):
            return error("Passengers must be a number.", 400)
        if not 1 <= passengers <= 60:
            return error("Passengers must be between 1 and 60.", 400)

        trip_at, problem = parse_trip_at(data.get("trip_at"))
        if problem:
            return error(problem, 400)

        db = get_db()
        car_id = None
        if kind == "car":
            try:
                car_id = int(data.get("car_id"))
            except (TypeError, ValueError):
                return error("Please choose a car.", 400)
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
            " (user_id, car_id, kind, customer_name, customer_email, customer_phone,"
            "  tour_name, pickup, dropoff, trip_at, passengers, notes)"
            " VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                car_id,
                kind,
                name,
                email,
                phone,
                tour_name,
                pickup,
                dropoff,
                trip_at,
                passengers,
                notes,
            ),
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
        if new_status in ("cancelled", "completed") and booking["car_id"] is not None:
            db.execute(
                "UPDATE cars SET status = 'available' WHERE id = ? AND status = 'booked'",
                (booking["car_id"],),
            )
        db.commit()
        if new_status == "confirmed":
            customer = None
            if booking["user_id"] is not None:
                customer = db.execute(
                    "SELECT first_name, last_name, email FROM users WHERE id = ?",
                    (booking["user_id"],),
                ).fetchone()
            elif booking["customer_email"]:
                customer = {
                    "first_name": booking["customer_name"],
                    "last_name": "",
                    "email": booking["customer_email"],
                }
            car = None
            if booking["car_id"] is not None:
                car = db.execute(
                    "SELECT name FROM cars WHERE id = ?", (booking["car_id"],)
                ).fetchone()
            label = car["name"] if car else (booking["tour_name"] or "your trip")
            if customer is not None and customer["email"]:
                _send_booking_confirmation_email(customer, booking, label)
        return jsonify({"ok": True, "status": new_status})

    @app.patch("/api/bookings/<int:booking_id>")
    @admin_required
    def booking_update(booking_id):
        data = body()
        db = get_db()
        booking = db.execute(
            "SELECT * FROM bookings WHERE id = ?", (booking_id,)
        ).fetchone()
        if booking is None:
            return error("This booking does not exist.", 404)
        if booking["user_id"] is None or booking["kind"] != "car":
            return error("Guest and tour bookings can only be updated by status.", 400)

        updates = {}
        for field, maximum in (("pickup", 150), ("dropoff", 150), ("notes", 500)):
            if field in data:
                updates[field] = text_value(data, field, maximum)
        if "passengers" in data:
            try:
                passengers = int(data["passengers"])
            except (TypeError, ValueError):
                return error("Passengers must be a number.", 400)
            if not 1 <= passengers <= 60:
                return error("Passengers must be between 1 and 60.", 400)
            updates["passengers"] = passengers
        if "trip_at" in data:
            moment, problem = parse_trip_at(
                data["trip_at"],
                require_future=booking["status"] in ("pending", "confirmed"),
            )
            if problem:
                return error(problem, 400)
            updates["trip_at"] = moment

        new_car_id = None
        if "car_id" in data:
            try:
                car_id = int(data["car_id"])
            except (TypeError, ValueError):
                return error("Please choose a car.", 400)
            car = db.execute("SELECT * FROM cars WHERE id = ?", (car_id,)).fetchone()
            if car is None:
                return error("This car does not exist.", 404)
            if car_id != booking["car_id"]:
                if booking["status"] in ("pending", "confirmed") and car["status"] != "available":
                    return error("This car is not available. Please choose another car.", 409)
                new_car_id = car_id
            updates["car_id"] = car_id

        if not updates:
            return error("Nothing to update.", 400)

        pickup = updates.get("pickup", booking["pickup"])
        dropoff = updates.get("dropoff", booking["dropoff"])
        if not pickup or not dropoff:
            return error("Please fill in all the fields.", 400)
        if pickup.casefold() == dropoff.casefold():
            return error("Pick-up and drop-off places must be different.", 400)

        final_car_id = updates.get("car_id", booking["car_id"])
        car = db.execute("SELECT * FROM cars WHERE id = ?", (final_car_id,)).fetchone()
        capacity = car_capacity(car)
        if updates.get("passengers", booking["passengers"]) > capacity:
            return error(f"This car can take up to {capacity} passengers.", 400)

        # Field names come only from the validated keys above.
        assignments = ", ".join(f"{field} = ?" for field in updates)
        db.execute(
            f"UPDATE bookings SET {assignments} WHERE id = ?",
            (*updates.values(), booking_id),
        )
        if new_car_id is not None and booking["status"] in ("pending", "confirmed"):
            # The trip moves to the new car: free the old one, take the new one.
            db.execute(
                "UPDATE cars SET status = 'available' WHERE id = ? AND status = 'booked'",
                (booking["car_id"],),
            )
            db.execute(
                "UPDATE cars SET status = 'booked' WHERE id = ? AND status = 'available'",
                (new_car_id,),
            )
        db.commit()
        return jsonify({"ok": True})

    @app.post("/api/admin/bookings/<int:booking_id>/payment")
    @admin_required
    def admin_booking_payment(booking_id):
        data = body()
        try:
            amount = round(float(data.get("amount")), 2)
        except (TypeError, ValueError):
            return error("Amount must be a number.", 400)
        if amount < 0:
            return error("Amount cannot be negative.", 400)
        if amount > 1000000000:
            return error("Amount is too large.", 400)
        method = text_value(data, "method", 40)
        if amount > 0 and not method:
            return error("Please enter how the payment was made.", 400)

        db = get_db()
        booking = db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
        if booking is None:
            return error("This booking does not exist.", 404)
        if booking["status"] == "cancelled":
            return error("This booking was cancelled.", 400)

        # An amount of 0 clears the recorded payment.
        paid_at = datetime.now().isoformat(timespec="minutes") if amount > 0 else ""
        paid_method = method if amount > 0 else ""
        db.execute(
            "UPDATE bookings SET paid_amount = ?, paid_method = ?, paid_at = ? WHERE id = ?",
            (amount, paid_method, paid_at, booking_id),
        )
        db.commit()
        return jsonify({"ok": True, "paid_amount": amount, "paid_method": paid_method})

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
        revenue = db.execute(
            "SELECT COALESCE(SUM(paid_amount), 0) AS total,"
            " COALESCE(SUM(paid_amount > 0), 0) AS paid_count"
            " FROM bookings WHERE status != 'cancelled'"
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
                "revenue": {
                    "total": revenue["total"],
                    "paid_bookings": revenue["paid_count"],
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

    # ---------- admin records ----------

    @app.get("/api/admin/users")
    @admin_required
    def admin_users():
        rows = get_db().execute(
            "SELECT id, first_name, last_name, email, phone, is_admin, active, created_at"
            " FROM users ORDER BY id"
        ).fetchall()
        return jsonify(
            [
                {
                    "id": row["id"],
                    "name": f"{row['first_name']} {row['last_name']}".strip(),
                    "email": row["email"],
                    "phone": row["phone"],
                    "admin": bool(row["is_admin"]),
                    "active": bool(row["active"]),
                    "created_at": row["created_at"],
                }
                for row in rows
            ]
        )

    @app.post("/api/admin/users")
    @admin_required
    def admin_user_create():
        data = body()
        first_name = text_value(data, "first_name", 50)
        last_name = text_value(data, "last_name", 50)
        email = text_value(data, "email", 150).lower()
        phone = text_value(data, "phone", 30)
        password = str(data.get("password") or "")
        admin = data.get("admin", False)

        if not isinstance(admin, bool):
            return error("Send admin as true or false.", 400)
        if not first_name or not last_name or not email or not password:
            return error("Please fill in all the fields.", 400)
        if not EMAIL_RE.match(email):
            return error("Please enter a valid email address.", 400)
        if not valid_phone(phone):
            return error("Please enter a valid phone number.", 400)
        if len(password) < 8:
            return error("Use at least 8 characters for the password.", 400)

        db = get_db()
        if db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            return error("Could not create the account with that email.", 409)

        cursor = db.execute(
            "INSERT INTO users (first_name, last_name, email, phone, password_hash,"
            " is_admin) VALUES (?, ?, ?, ?, ?, ?)",
            (
                first_name,
                last_name,
                email,
                phone,
                generate_password_hash(password),
                int(admin),
            ),
        )
        db.commit()
        created = db.execute(
            "SELECT id, first_name, last_name, email, phone, is_admin, active,"
            " created_at FROM users WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
        return (
            jsonify(
                {
                    "ok": True,
                    "user": {
                        "id": created["id"],
                        "name": f"{created['first_name']} {created['last_name']}".strip(),
                        "email": created["email"],
                        "phone": created["phone"],
                        "admin": bool(created["is_admin"]),
                        "active": bool(created["active"]),
                        "created_at": created["created_at"],
                    },
                }
            ),
            201,
        )

    @app.delete("/api/admin/users/<int:user_id>")
    @admin_required
    def admin_user_delete(user_id):
        db = get_db()
        target = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if target is None:
            return error("This account does not exist.", 404)
        if user_id == g.user["id"]:
            return error("You cannot delete your own account.", 400)
        if target["is_admin"]:
            admins = db.execute(
                "SELECT COUNT(*) AS n FROM users WHERE is_admin = 1"
            ).fetchone()["n"]
            if admins <= 1:
                return error("At least one admin account is required.", 400)
        used = db.execute(
            "SELECT 1 FROM bookings WHERE user_id = ? LIMIT 1", (user_id,)
        ).fetchone()
        if used is not None:
            return error(
                "This account has bookings in its history. Deactivate it instead.",
                409,
            )
        db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        db.commit()
        return jsonify({"ok": True})

    @app.post("/api/admin/users/<int:user_id>/admin")
    @admin_required
    def admin_user_role(user_id):
        value = body().get("admin")
        if not isinstance(value, bool):
            return error("Send admin as true or false.", 400)

        db = get_db()
        target = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if target is None:
            return error("This account does not exist.", 404)

        if not value:
            if user_id == g.user["id"]:
                return error("You cannot remove your own admin access.", 400)
            if target["is_admin"]:
                admins = db.execute(
                    "SELECT COUNT(*) AS n FROM users WHERE is_admin = 1"
                ).fetchone()["n"]
                if admins <= 1:
                    return error("At least one admin account is required.", 400)

        db.execute(
            "UPDATE users SET is_admin = ? WHERE id = ?", (int(value), user_id)
        )
        db.commit()
        updated = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return jsonify({"ok": True, "user": user_json(updated)})

    @app.post("/api/admin/users/<int:user_id>/active")
    @admin_required
    def admin_user_active(user_id):
        value = body().get("active")
        if not isinstance(value, bool):
            return error("Send active as true or false.", 400)

        db = get_db()
        target = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if target is None:
            return error("This account does not exist.", 404)
        if target["id"] == g.user["id"]:
            return error("You cannot change the state of your own account.", 400)
        if not value and target["is_admin"] and target["active"]:
            active_admins = db.execute(
                "SELECT COUNT(*) AS n FROM users WHERE is_admin = 1 AND active = 1"
            ).fetchone()["n"]
            if active_admins <= 1:
                return error("At least one active admin account is required.", 400)

        db.execute("UPDATE users SET active = ? WHERE id = ?", (int(value), user_id))
        db.commit()
        return jsonify({"ok": True, "active": value})

    @app.post("/api/admin/users/<int:user_id>/password")
    @admin_required
    def admin_user_password(user_id):
        password = str(body().get("password") or "")
        if len(password) < 8:
            return error("Use at least 8 characters for the password.", 400)

        db = get_db()
        exists = db.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone()
        if exists is None:
            return error("This account does not exist.", 404)
        db.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (generate_password_hash(password), user_id),
        )
        db.commit()
        return jsonify({"ok": True})

    @app.get("/api/admin/messages")
    @admin_required
    def admin_messages():
        rows = get_db().execute(
            "SELECT id, name, email, phone, service, message, handled, created_at"
            " FROM messages ORDER BY id DESC"
        ).fetchall()
        messages = []
        for row in rows:
            message = dict(row)
            message["handled"] = bool(message["handled"])
            messages.append(message)
        return jsonify(messages)

    @app.get("/api/admin/comments")
    @admin_required
    def admin_comments():
        rows = get_db().execute(
            "SELECT id, user_id, name, rating, text, handled, created_at"
            " FROM comments ORDER BY id DESC"
        ).fetchall()
        comments = []
        for row in rows:
            comment = dict(row)
            comment["handled"] = bool(comment["handled"])
            comments.append(comment)
        return jsonify(comments)

    @app.post("/api/admin/messages/<int:message_id>/handled")
    @admin_required
    def admin_message_handled(message_id):
        value = body().get("handled")
        if not isinstance(value, bool):
            return error("Send handled as true or false.", 400)

        db = get_db()
        message = db.execute("SELECT id FROM messages WHERE id = ?", (message_id,)).fetchone()
        if message is None:
            return error("This message does not exist.", 404)

        db.execute("UPDATE messages SET handled = ? WHERE id = ?", (int(value), message_id))
        db.commit()
        return jsonify({"ok": True, "handled": value})

    @app.post("/api/admin/comments/<int:comment_id>/handled")
    @admin_required
    def admin_comment_handled(comment_id):
        value = body().get("handled")
        if not isinstance(value, bool):
            return error("Send handled as true or false.", 400)

        db = get_db()
        comment = db.execute("SELECT id FROM comments WHERE id = ?", (comment_id,)).fetchone()
        if comment is None:
            return error("This comment does not exist.", 404)

        db.execute("UPDATE comments SET handled = ? WHERE id = ?", (int(value), comment_id))
        db.commit()
        return jsonify({"ok": True, "handled": value})

    @app.delete("/api/admin/messages/<int:message_id>")
    @admin_required
    def admin_message_delete(message_id):
        db = get_db()
        deleted = db.execute("DELETE FROM messages WHERE id = ?", (message_id,))
        db.commit()
        if deleted.rowcount == 0:
            return error("This message does not exist.", 404)
        return jsonify({"ok": True})

    @app.delete("/api/admin/comments/<int:comment_id>")
    @admin_required
    def admin_comment_delete(comment_id):
        db = get_db()
        deleted = db.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
        db.commit()
        if deleted.rowcount == 0:
            return error("This comment does not exist.", 404)
        return jsonify({"ok": True})

    # ---------- admin fleet management ----------

    @app.post("/api/admin/cars")
    @admin_required
    def admin_car_create():
        data = body()
        name = text_value(data, "name", CAR_TEXT_FIELDS["name"])
        car_type = text_value(data, "type", CAR_TEXT_FIELDS["type"])
        if not name or not car_type:
            return error("Please fill in the car name and type.", 400)
        capacity, problem = parse_capacity(data.get("capacity", 4))
        if problem:
            return error(problem, 400)

        db = get_db()
        cursor = db.execute(
            "INSERT INTO cars (name, type, description, image, capacity, price, week, specs)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                name,
                car_type,
                text_value(data, "description", CAR_TEXT_FIELDS["description"]),
                text_value(data, "image", CAR_TEXT_FIELDS["image"]),
                capacity,
                text_value(data, "price", CAR_TEXT_FIELDS["price"]),
                text_value(data, "week", CAR_TEXT_FIELDS["week"]),
                _car_specs_value(data.get("specs")),
            ),
        )
        db.commit()
        car = db.execute("SELECT * FROM cars WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return jsonify({"ok": True, "car": car_json(car)}), 201

    @app.patch("/api/admin/cars/<int:car_id>")
    @admin_required
    def admin_car_update(car_id):
        data = body()
        db = get_db()
        car = db.execute("SELECT * FROM cars WHERE id = ?", (car_id,)).fetchone()
        if car is None:
            return error("This car does not exist.", 404)

        updates = {}
        for field, maximum in CAR_TEXT_FIELDS.items():
            if field in data:
                if field == "specs":
                    updates[field] = _car_specs_value(data[field])
                else:
                    updates[field] = text_value(data, field, maximum)
        if "capacity" in data:
            capacity, problem = parse_capacity(data["capacity"])
            if problem:
                return error(problem, 400)
            updates["capacity"] = capacity
        if not updates:
            return error("Nothing to update.", 400)
        if updates.get("name", car["name"]).strip() == "":
            return error("Please fill in the car name and type.", 400)
        if updates.get("type", car["type"]).strip() == "":
            return error("Please fill in the car name and type.", 400)

        # Field names come only from CAR_TEXT_FIELDS plus the validated
        # "capacity" key above, so building the SET clause is safe.
        assignments = ", ".join(f"{field} = ?" for field in updates)
        db.execute(
            f"UPDATE cars SET {assignments} WHERE id = ?",
            (*updates.values(), car_id),
        )
        db.commit()
        updated = db.execute("SELECT * FROM cars WHERE id = ?", (car_id,)).fetchone()
        return jsonify({"ok": True, "car": car_json(updated)})

    @app.delete("/api/admin/cars/<int:car_id>")
    @admin_required
    def admin_car_delete(car_id):
        db = get_db()
        car = db.execute("SELECT id FROM cars WHERE id = ?", (car_id,)).fetchone()
        if car is None:
            return error("This car does not exist.", 404)
        used = db.execute(
            "SELECT 1 FROM bookings WHERE car_id = ? LIMIT 1", (car_id,)
        ).fetchone()
        if used is not None:
            return error(
                "This car has bookings in its history. Set it to maintenance to hide it.",
                409,
            )
        db.execute("DELETE FROM cars WHERE id = ?", (car_id,))
        db.commit()
        return jsonify({"ok": True})

    # ---------- admin fares ----------

    @app.get("/api/admin/fares")
    @admin_required
    def admin_fares():
        rows = get_db().execute(
            "SELECT id, key, tag, name, amount, currency, note, flw_link, active"
            " FROM fares ORDER BY id"
        ).fetchall()
        return jsonify([fare_json(row) for row in rows])

    @app.post("/api/admin/fares")
    @admin_required
    def admin_fare_create():
        values, problem = _fare_payload(body(), partial=False)
        if problem:
            return error(problem, 400)
        db = get_db()
        if db.execute("SELECT 1 FROM fares WHERE key = ?", (values["key"],)).fetchone():
            return error("Another fare already uses that code.", 409)
        cursor = db.execute(
            "INSERT INTO fares (key, tag, name, amount, currency, note, flw_link)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (values["key"], values["tag"], values["name"], values["amount"],
             values["currency"], values["note"], values["flw_link"]),
        )
        db.commit()
        row = db.execute("SELECT * FROM fares WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return jsonify({"ok": True, "fare": fare_json(row)}), 201

    @app.patch("/api/admin/fares/<int:fare_id>")
    @admin_required
    def admin_fare_update(fare_id):
        values, problem = _fare_payload(body(), partial=True)
        if problem:
            return error(problem, 400)
        if not values:
            return error("Nothing to update.", 400)
        db = get_db()
        fare = db.execute("SELECT * FROM fares WHERE id = ?", (fare_id,)).fetchone()
        if fare is None:
            return error("This fare does not exist.", 404)
        if "key" in values and values["key"] != fare["key"]:
            clash = db.execute(
                "SELECT 1 FROM fares WHERE key = ? AND id != ?", (values["key"], fare_id)
            ).fetchone()
            if clash:
                return error("Another fare already uses that code.", 409)

        # Field names come only from the validated keys in _fare_payload.
        assignments = ", ".join(f"{field} = ?" for field in values)
        db.execute(
            f"UPDATE fares SET {assignments} WHERE id = ?",
            (*values.values(), fare_id),
        )
        db.commit()
        updated = db.execute("SELECT * FROM fares WHERE id = ?", (fare_id,)).fetchone()
        return jsonify({"ok": True, "fare": fare_json(updated)})

    @app.delete("/api/admin/fares/<int:fare_id>")
    @admin_required
    def admin_fare_delete(fare_id):
        db = get_db()
        deleted = db.execute("DELETE FROM fares WHERE id = ?", (fare_id,))
        db.commit()
        if deleted.rowcount == 0:
            return error("This fare does not exist.", 404)
        return jsonify({"ok": True})

    # ---------- admin exports ----------

    @app.get("/api/admin/export/bookings.csv")
    @admin_required
    def admin_export_bookings():
        rows = get_db().execute(
            "SELECT b.id,"
            " COALESCE(NULLIF(b.customer_name, ''),"
            "   TRIM(COALESCE(u.first_name, '') || ' ' || COALESCE(u.last_name, ''))) AS customer,"
            " COALESCE(NULLIF(b.customer_email, ''), u.email) AS email,"
            " COALESCE(NULLIF(b.customer_phone, ''), u.phone) AS phone,"
            " COALESCE(c.name, NULLIF(b.tour_name, ''), '') AS car, b.kind,"
            " b.pickup, b.dropoff, b.trip_at, b.passengers, b.status,"
            " b.paid_amount, b.paid_method, b.paid_at, b.created_at"
            " FROM bookings b"
            " LEFT JOIN cars c ON c.id = b.car_id"
            " LEFT JOIN users u ON u.id = b.user_id"
            " ORDER BY b.id"
        ).fetchall()
        header = [
            "id", "customer", "email", "phone", "car", "kind", "pickup", "dropoff",
            "trip_at", "passengers", "status", "paid_amount", "paid_method", "paid_at",
            "created_at",
        ]
        return _csv_response("bookings.csv", header, [tuple(r[k] for k in header) for r in rows])

    @app.get("/api/admin/export/messages.csv")
    @admin_required
    def admin_export_messages():
        rows = get_db().execute(
            "SELECT id, name, email, phone, service, message,"
            " CASE WHEN handled = 1 THEN 'yes' ELSE 'no' END AS handled, created_at"
            " FROM messages ORDER BY id"
        ).fetchall()
        header = ["id", "name", "email", "phone", "service", "message", "handled", "created_at"]
        return _csv_response("messages.csv", header, [tuple(r[k] for k in header) for r in rows])

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
