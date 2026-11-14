"""
Safarnama Diaries - backend
===========================
Serves the static website AND handles the three forms:

  POST /api/contact      Contact & Review form   (contact.html)
  POST /api/newsletter   Newsletter signup       (index.html)
  POST /api/stories      Share Your Story form   (submit-story.html, with photo)

Everything is stored in SQLite (data/safarnama.db). Uploaded photos go to
data/uploads/ and are NOT publicly served. Only the admin can view them.

Admin dashboard: /admin  (HTTP Basic Auth)
  - username: admin
  - password: the ADMIN_PASSWORD environment variable
  - if ADMIN_PASSWORD is not set, the admin area is disabled.

Run:
  pip install -r requirements.txt
  ADMIN_PASSWORD="choose-a-strong-one" python server.py
"""

import csv
import hmac
import io
import os
import re
import secrets
import sqlite3
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

from flask import (
    Flask, Response, abort, g, jsonify, redirect, render_template_string,
    request, send_from_directory,
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "safarnama.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_PHOTO_BYTES = 5 * 1024 * 1024  # 5 MB
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

# Only these site files/folders are ever served publicly.
PUBLIC_DIRS = {"css", "js", "images"}
PUBLIC_PAGES_SUFFIX = ".html"

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = MAX_PHOTO_BYTES + 512 * 1024  # photo + form fields


# --------------------------------------------------------------------------
# Database
# --------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    age INTEGER,
    phone TEXT,
    education TEXT,
    profession TEXT,
    heard_from TEXT,
    visit_again TEXT,
    rating INTEGER,
    comment TEXT,
    newsletter INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS subscribers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    source TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    title TEXT NOT NULL,
    destination TEXT,
    travel_date TEXT,
    story TEXT NOT NULL,
    photo TEXT,
    consent INTEGER NOT NULL
);
"""


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.executescript(SCHEMA)


init_db()


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


# --------------------------------------------------------------------------
# Helpers: validation, rate limiting
# --------------------------------------------------------------------------
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[0-9+\-\s()]{7,20}$")

EDUCATION = {"Matric", "Intermediate", "Bachelor's", "Master's", "Other"}
HEARD_FROM = {"friend", "social", "search", "class", "other"}
VISIT_AGAIN = {"yes", "maybe", "no"}
DESTINATIONS = {
    "Hunza Valley", "Swat Valley", "Lahore Walled City", "Fairy Meadows",
    "Gwadar", "Tharparkar", "Other",
}


class ValidationError(Exception):
    def __init__(self, errors):
        self.errors = errors


def field(name, max_len):
    """Read a form field, trimmed and length-capped."""
    return (request.form.get(name) or "").strip()[:max_len]


def check_email(value, errors, key="email"):
    if not value:
        errors[key] = "Email is required."
    elif len(value) > 254 or not EMAIL_RE.match(value):
        errors[key] = "Please enter a valid email address."


# Simple in-memory rate limiter: N requests per window per IP per endpoint.
_hits = defaultdict(deque)


def rate_limited(limit=8, window=600):
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "?").split(",")[0].strip()
    key = (ip, request.endpoint)
    q = _hits[key]
    now = time.time()
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        return True
    q.append(now)
    return False


def ok(message, **extra):
    """JSON for fetch(); a small thank-you page for plain form posts (no JS)."""
    if request.accept_mimetypes.best == "application/json" or request.headers.get("X-Requested-With") == "fetch":
        return jsonify(ok=True, message=message, **extra)
    return Response(
        f"<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Thank you</title><body style='font-family:sans-serif;max-width:32rem;margin:4rem auto;padding:0 1rem'>"
        f"<h1>Thank you!</h1><p>{message}</p><p><a href='/index.html'>Back to home</a></p></body>",
        mimetype="text/html",
    )


def fail(errors, status=400):
    if request.accept_mimetypes.best == "application/json" or request.headers.get("X-Requested-With") == "fetch":
        return jsonify(ok=False, errors=errors), status
    items = "".join(f"<li>{v}</li>" for v in errors.values())  # messages are server-defined constants
    return Response(
        f"<!doctype html><meta charset='utf-8'><title>Error</title>"
        f"<body style='font-family:sans-serif;max-width:32rem;margin:4rem auto'>"
        f"<h1>Please fix the following</h1><ul>{items}</ul>"
        f"<p><a href='javascript:history.back()'>Go back</a></p></body>",
        status=status, mimetype="text/html",
    )


# --------------------------------------------------------------------------
# API: newsletter
# --------------------------------------------------------------------------
def add_subscriber(db, email, source):
    """Insert if new. Returns True if newly added, False if already subscribed."""
    cur = db.execute(
        "INSERT OR IGNORE INTO subscribers (created_at, email, source) VALUES (?, ?, ?)",
        (now_iso(), email, source),
    )
    return cur.rowcount == 1


@app.post("/api/newsletter")
def api_newsletter():
    if rate_limited(limit=10):
        return fail({"form": "Too many requests. Please try again later."}, 429)

    email = field("email", 254)
    errors = {}
    check_email(email, errors)
    if errors:
        return fail(errors)

    db = get_db()
    add_subscriber(db, email, "newsletter-form")
    db.commit()
    # Same message either way so the form can't be used to probe who is subscribed.
    return ok("You're subscribed. Thank you for joining Safarnama Diaries!")


# --------------------------------------------------------------------------
# API: contact & review
# --------------------------------------------------------------------------
@app.post("/api/contact")
def api_contact():
    if rate_limited(limit=6):
        return fail({"form": "Too many submissions. Please try again later."}, 429)

    errors = {}
    name = field("name", 100)
    email = field("email", 254)
    phone = field("phone", 20)
    education = field("education", 30)
    profession = field("profession", 100)
    heard_from = field("heard_from", 20)
    visit_again = field("visit_again", 10)
    comment = field("comment", 3000)
    newsletter = 1 if request.form.get("newsletter") == "yes" else 0

    if not name:
        errors["name"] = "Name is required."
    check_email(email, errors)

    age = None
    if field("age", 5):
        try:
            age = int(field("age", 5))
            if not 10 <= age <= 100:
                raise ValueError
        except ValueError:
            errors["age"] = "Age must be a number between 10 and 100."

    if phone and not PHONE_RE.match(phone):
        errors["phone"] = "Please enter a valid phone number."
    if education and education not in EDUCATION:
        errors["education"] = "Invalid option."
    if heard_from and heard_from not in HEARD_FROM:
        errors["heard_from"] = "Invalid option."
    if visit_again and visit_again not in VISIT_AGAIN:
        errors["visit_again"] = "Invalid option."

    rating = None
    if field("rating", 2):
        try:
            rating = int(field("rating", 2))
            if not 1 <= rating <= 5:
                raise ValueError
        except ValueError:
            errors["rating"] = "Rating must be between 1 and 5."

    if errors:
        return fail(errors)

    db = get_db()
    db.execute(
        """INSERT INTO contacts (created_at, name, email, age, phone, education,
               profession, heard_from, visit_again, rating, comment, newsletter)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (now_iso(), name, email, age, phone or None, education or None,
         profession or None, heard_from or None, visit_again or None,
         rating, comment or None, newsletter),
    )
    if newsletter:
        add_subscriber(db, email, "contact-form")
    db.commit()
    return ok("Thank you! Your message and feedback have been received.")


# --------------------------------------------------------------------------
# API: story submission (with optional photo)
# --------------------------------------------------------------------------
def sniff_image(head: bytes):
    """Identify the image type from its first bytes, ignoring the client's claims."""
    if head.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    return None


@app.post("/api/stories")
def api_stories():
    if rate_limited(limit=4):
        return fail({"form": "Too many submissions. Please try again later."}, 429)

    errors = {}
    name = field("name", 100)
    email = field("email", 254)
    title = field("title", 100)
    destination = field("destination", 50)
    travel_date = field("travel_date", 10)
    story = field("story", 20000)

    if not name:
        errors["name"] = "Name is required."
    check_email(email, errors)
    if not title:
        errors["title"] = "Story title is required."
    if len(story) < 50:
        errors["story"] = "Please write at least 50 characters."
    if destination and destination not in DESTINATIONS:
        errors["destination"] = "Invalid destination."
    if travel_date:
        try:
            datetime.strptime(travel_date, "%Y-%m-%d")
        except ValueError:
            errors["travel_date"] = "Invalid date."
    if request.form.get("consent") != "yes":
        errors["consent"] = "You must confirm the rights/consent box."

    photo_bytes, photo_ext = None, None
    upload = request.files.get("photo")
    if upload and upload.filename:
        photo_bytes = upload.read(MAX_PHOTO_BYTES + 1)
        if len(photo_bytes) > MAX_PHOTO_BYTES:
            errors["photo"] = "Photo must be 5 MB or smaller."
        else:
            photo_ext = sniff_image(photo_bytes[:16])
            if not photo_ext:
                errors["photo"] = "Photo must be a JPG, PNG, WebP or GIF image."

    if errors:
        return fail(errors)

    photo_name = None
    if photo_bytes:
        photo_name = f"{secrets.token_hex(16)}{photo_ext}"  # random name, never the user's
        (UPLOAD_DIR / photo_name).write_bytes(photo_bytes)

    db = get_db()
    db.execute(
        """INSERT INTO stories (created_at, name, email, title, destination,
               travel_date, story, photo, consent)
           VALUES (?,?,?,?,?,?,?,?,1)""",
        (now_iso(), name, email, title, destination or None,
         travel_date or None, story, photo_name),
    )
    db.commit()
    return ok("Thank you! Your story has been submitted and will be reviewed by our team.")


@app.errorhandler(413)
def too_large(_e):
    return fail({"photo": "Upload is too large (max 5 MB)."}, 413)


# --------------------------------------------------------------------------
# Admin dashboard (read-only)
# --------------------------------------------------------------------------
def require_admin():
    if not ADMIN_PASSWORD:
        abort(404)  # admin disabled until a password is configured
    auth = request.authorization
    if (
        not auth
        or not hmac.compare_digest(auth.username or "", "admin")
        or not hmac.compare_digest(auth.password or "", ADMIN_PASSWORD)
    ):
        return Response(
            "Login required.", 401,
            {"WWW-Authenticate": 'Basic realm="Safarnama Admin"'},
        )
    return None


ADMIN_TEMPLATE = """
<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>Admin | Safarnama Diaries</title>
<style>
 body{font-family:system-ui,sans-serif;margin:0;padding:1.5rem;background:#f6f5f1;color:#222}
 h1{margin-top:0} h2{margin-top:2.5rem}
 .box{overflow-x:auto;background:#fff;border:1px solid #ddd;border-radius:8px}
 table{border-collapse:collapse;width:100%;font-size:.9rem}
 th,td{padding:.5rem .7rem;border-bottom:1px solid #eee;text-align:left;vertical-align:top}
 th{background:#fafafa;white-space:nowrap}
 td.long{min-width:18rem;white-space:pre-wrap}
 a.btn{display:inline-block;margin-left:.5rem;font-size:.85rem}
 .muted{color:#777}
</style></head><body>
<h1>Safarnama Diaries &mdash; Admin</h1>
<p class="muted">{{ counts.contacts }} reviews &middot; {{ counts.subscribers }} subscribers &middot; {{ counts.stories }} stories</p>

<h2>Submitted stories <a class="btn" href="/admin/export/stories.csv">CSV</a></h2>
<div class="box"><table>
<tr><th>ID</th><th>Date (UTC)</th><th>Name</th><th>Email</th><th>Title</th><th>Destination</th><th>Travel date</th><th>Story</th><th>Photo</th></tr>
{% for r in stories %}<tr>
<td>{{ r.id }}</td><td>{{ r.created_at }}</td><td>{{ r.name }}</td><td>{{ r.email }}</td><td>{{ r.title }}</td>
<td>{{ r.destination or '' }}</td><td>{{ r.travel_date or '' }}</td><td class="long">{{ r.story }}</td>
<td>{% if r.photo %}<a href="/admin/uploads/{{ r.photo }}" target="_blank" rel="noopener">view</a>{% endif %}</td>
</tr>{% else %}<tr><td colspan="9" class="muted">No stories yet.</td></tr>{% endfor %}
</table></div>

<h2>Contact &amp; reviews <a class="btn" href="/admin/export/contacts.csv">CSV</a></h2>
<div class="box"><table>
<tr><th>ID</th><th>Date (UTC)</th><th>Name</th><th>Email</th><th>Age</th><th>Phone</th><th>Education</th><th>Profession</th><th>Heard from</th><th>Visit again</th><th>Rating</th><th>Comment</th><th>Newsletter</th></tr>
{% for r in contacts %}<tr>
<td>{{ r.id }}</td><td>{{ r.created_at }}</td><td>{{ r.name }}</td><td>{{ r.email }}</td><td>{{ r.age or '' }}</td>
<td>{{ r.phone or '' }}</td><td>{{ r.education or '' }}</td><td>{{ r.profession or '' }}</td><td>{{ r.heard_from or '' }}</td>
<td>{{ r.visit_again or '' }}</td><td>{{ r.rating or '' }}</td><td class="long">{{ r.comment or '' }}</td><td>{{ 'yes' if r.newsletter else '' }}</td>
</tr>{% else %}<tr><td colspan="13" class="muted">No reviews yet.</td></tr>{% endfor %}
</table></div>

<h2>Newsletter subscribers <a class="btn" href="/admin/export/subscribers.csv">CSV</a></h2>
<div class="box"><table>
<tr><th>ID</th><th>Date (UTC)</th><th>Email</th><th>Source</th></tr>
{% for r in subscribers %}<tr><td>{{ r.id }}</td><td>{{ r.created_at }}</td><td>{{ r.email }}</td><td>{{ r.source }}</td></tr>
{% else %}<tr><td colspan="4" class="muted">No subscribers yet.</td></tr>{% endfor %}
</table></div>
</body></html>
"""

EXPORTS = {"stories", "contacts", "subscribers"}


@app.get("/admin")
def admin_home():
    denied = require_admin()
    if denied:
        return denied
    db = get_db()
    data = {t: db.execute(f"SELECT * FROM {t} ORDER BY id DESC").fetchall() for t in EXPORTS}
    counts = {t: len(rows) for t, rows in data.items()}
    resp = Response(render_template_string(ADMIN_TEMPLATE, counts=counts, **data), mimetype="text/html")
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/admin/export/<table>.csv")
def admin_export(table):
    denied = require_admin()
    if denied:
        return denied
    if table not in EXPORTS:  # allow-list: table name is never taken from input directly
        abort(404)
    cur = get_db().execute(f"SELECT * FROM {table} ORDER BY id")
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([d[0] for d in cur.description])
    for row in cur:
        # Neutralise spreadsheet formula injection (=, +, -, @ at the start of a cell).
        w.writerow([("'" + v) if isinstance(v, str) and v[:1] in "=+-@" else v for v in tuple(row)])
    return Response(
        out.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={table}.csv", "Cache-Control": "no-store"},
    )


@app.get("/admin/uploads/<filename>")
def admin_upload(filename):
    denied = require_admin()
    if denied:
        return denied
    if not re.fullmatch(r"[0-9a-f]{32}\.(jpg|png|webp|gif)", filename):
        abort(404)
    resp = send_from_directory(UPLOAD_DIR, filename)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


# --------------------------------------------------------------------------
# Static website (allow-list only, so server.py, data/ and the .docx are never exposed)
# --------------------------------------------------------------------------
@app.get("/")
def home():
    return redirect("/index.html")


@app.get("/<path:path>")
def site(path):
    parts = Path(path).parts
    if len(parts) == 1 and path.endswith(PUBLIC_PAGES_SUFFIX):
        return send_from_directory(BASE_DIR, path)
    if len(parts) >= 2 and parts[0] in PUBLIC_DIRS:
        return send_from_directory(BASE_DIR, path)
    abort(404)


@app.after_request
def security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    return resp


if __name__ == "__main__":
    if not ADMIN_PASSWORD:
        print("NOTE: ADMIN_PASSWORD is not set, so /admin is disabled.")
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=False)
