"""Vanalaya Studio website: public portfolio site plus a private admin panel.

Run locally:   python app.py
Production:    gunicorn app:app   (see render.yaml)
"""
import os
import re
import secrets
import smtplib
import sqlite3
import threading
import time
import uuid
from datetime import datetime
from email.message import EmailMessage
from functools import wraps

from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   send_from_directory, session, url_for, Response)
from markupsafe import Markup, escape
from PIL import Image, ImageOps
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import seed

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
DB_PATH = os.path.join(DATA_DIR, "vanalaya.db")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")

ALLOWED_EXT = {"jpg", "jpeg", "png", "webp"}
ENQUIRY_STATUSES = ["new", "contacted", "closed"]
PROJECT_TYPES = ["Residential", "Commercial", "Eco-friendly / Bamboo", "Hospitality",
                 "Interior design", "Civil engineering / sanction drawings", "Other"]


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", ""),
        DATA_DIR=DATA_DIR,
        MAX_CONTENT_LENGTH=40 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
        PERMANENT_SESSION_LIFETIME=60 * 60 * 8,
        SITE_URL=os.environ.get("SITE_URL", "").rstrip("/"),
        TESTING=False,
    )
    if test_config:
        app.config.update(test_config)

    data_dir = app.config["DATA_DIR"]
    app.config["DB_PATH"] = os.path.join(data_dir, "vanalaya.db")
    app.config["UPLOAD_DIR"] = os.path.join(data_dir, "uploads")
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)

    if not app.config["SECRET_KEY"]:
        key_file = os.path.join(data_dir, "secret_key.txt")
        if os.path.exists(key_file):
            app.config["SECRET_KEY"] = open(key_file).read().strip()
        else:
            app.config["SECRET_KEY"] = secrets.token_hex(32)
            with open(key_file, "w") as f:
                f.write(app.config["SECRET_KEY"])

    if os.environ.get("BEHIND_PROXY") == "1":
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    register_db(app)
    with app.app_context():
        init_db(app)
    register_filters(app)
    register_routes(app)
    return app


# ---------------------------------------------------------------- database

def register_db(app):
    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DB_PATH"])
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        return g.db

    app.get_db = get_db

    @app.teardown_appcontext
    def close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            db.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    location TEXT DEFAULT '',
    area TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    studio_role TEXT DEFAULT '',
    video_url TEXT DEFAULT '',
    featured INTEGER DEFAULT 0,
    published INTEGER DEFAULT 1,
    sort_order INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS project_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    caption TEXT DEFAULT '',
    sort_order INTEGER DEFAULT 0,
    is_cover INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS categories (
    slug TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    blurb TEXT DEFAULT '',
    sort_order INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    icon TEXT DEFAULT 'home',
    sort_order INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS testimonials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_name TEXT NOT NULL,
    project_name TEXT DEFAULT '',
    quote TEXT NOT NULL,
    published INTEGER DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS enquiries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT DEFAULT '',
    email TEXT DEFAULT '',
    project_type TEXT DEFAULT '',
    message TEXT NOT NULL,
    status TEXT DEFAULT 'new',
    private_note TEXT DEFAULT '',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS site_settings (
    key TEXT PRIMARY KEY,
    value TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS admin_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    last_login TEXT
);
"""


def init_db(app):
    db = app.get_db()
    db.executescript(SCHEMA)

    if db.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
        for i, (slug, name, blurb) in enumerate(seed.CATEGORIES):
            db.execute("INSERT INTO categories (slug, name, blurb, sort_order) VALUES (?,?,?,?)",
                       (slug, name, blurb, i))
    if db.execute("SELECT COUNT(*) FROM services").fetchone()[0] == 0:
        for i, (title, desc, icon) in enumerate(seed.SERVICES):
            db.execute("INSERT INTO services (title, description, icon, sort_order) VALUES (?,?,?,?)",
                       (title, desc, icon, i))
    if db.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0:
        for i, p in enumerate(seed.PROJECTS):
            slug, title, cat, loc, summary, desc, tags, role, featured = p
            db.execute(
                "INSERT INTO projects (slug, title, category, location, summary, description, tags,"
                " studio_role, featured, published, sort_order) VALUES (?,?,?,?,?,?,?,?,?,1,?)",
                (slug, title, cat, loc, summary, desc, tags, role, featured, i))
    for k, v in seed.SETTINGS.items():
        db.execute("INSERT OR IGNORE INTO site_settings (key, value) VALUES (?, ?)", (k, v))

    if db.execute("SELECT COUNT(*) FROM admin_users").fetchone()[0] == 0:
        password = os.environ.get("ADMIN_PASSWORD")
        generated = False
        if not password:
            password = secrets.token_urlsafe(9)
            generated = True
        username = os.environ.get("ADMIN_USERNAME", "admin")
        db.execute("INSERT INTO admin_users (username, password_hash) VALUES (?, ?)",
                   (username, generate_password_hash(password)))
        if generated:
            path = os.path.join(app.config["DATA_DIR"], "first_admin_login.txt")
            with open(path, "w") as f:
                f.write(f"username: {username}\npassword: {password}\n"
                        "Change this password after your first login, then delete this file.\n")
            print(f"\n*** First admin login -> username: {username}  password: {password}\n"
                  f"*** (also saved in {path})\n")
    db.commit()


# ---------------------------------------------------------------- helpers

def slugify(text):
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return text or "project"


def unique_slug(db, title, exclude_id=None):
    base = slugify(title)
    slug, n = base, 2
    while True:
        row = db.execute("SELECT id FROM projects WHERE slug = ?", (slug,)).fetchone()
        if not row or (exclude_id and row["id"] == exclude_id):
            return slug
        slug = f"{base}-{n}"
        n += 1


def get_settings(db):
    return {r["key"]: r["value"] for r in db.execute("SELECT key, value FROM site_settings")}


def save_image(file_storage, upload_dir):
    """Validate, resize and store an uploaded photo. Returns the stored base name or None."""
    name = secure_filename(file_storage.filename or "")
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_EXT:
        return None
    try:
        img = Image.open(file_storage.stream)
        img = ImageOps.exif_transpose(img)
        img = img.convert("RGB")
    except Exception:
        return None
    base = uuid.uuid4().hex[:16]
    large = img.copy()
    large.thumbnail((1800, 1800))
    large.save(os.path.join(upload_dir, f"{base}.jpg"), "JPEG", quality=84, optimize=True)
    thumb = img.copy()
    thumb.thumbnail((700, 700))
    thumb.save(os.path.join(upload_dir, f"{base}_t.jpg"), "JPEG", quality=80, optimize=True)
    return base


def remove_image_files(upload_dir, base):
    for suffix in (".jpg", "_t.jpg"):
        path = os.path.join(upload_dir, base + suffix)
        if os.path.exists(path):
            os.remove(path)


def send_enquiry_email(app, enquiry, settings):
    host = os.environ.get("SMTP_HOST")
    if not host:
        app.logger.info("New enquiry from %s (SMTP not configured, no email sent)", enquiry["name"])
        return
    to = os.environ.get("NOTIFY_EMAIL") or settings.get("email")

    def worker():
        try:
            msg = EmailMessage()
            msg["Subject"] = f"New website enquiry from {enquiry['name']}"
            msg["From"] = os.environ.get("SMTP_USER", to)
            msg["To"] = to
            msg.set_content(
                f"Name: {enquiry['name']}\nPhone: {enquiry['phone']}\nEmail: {enquiry['email']}\n"
                f"Project type: {enquiry['project_type']}\n\n{enquiry['message']}\n")
            with smtplib.SMTP(host, int(os.environ.get("SMTP_PORT", "587")), timeout=15) as s:
                s.starttls()
                if os.environ.get("SMTP_USER"):
                    s.login(os.environ["SMTP_USER"], os.environ.get("SMTP_PASSWORD", ""))
                s.send_message(msg)
        except Exception as exc:  # never break the visitor's request
            app.logger.warning("Enquiry email failed: %s", exc)

    threading.Thread(target=worker, daemon=True).start()


_hits = {}


def too_many(key, limit, window):
    now = time.time()
    hits = [t for t in _hits.get(key, []) if now - t < window]
    _hits[key] = hits
    if len(hits) >= limit:
        return True
    hits.append(now)
    return False


def register_filters(app):
    @app.template_filter("paragraphs")
    def paragraphs(text):
        parts = [p.strip() for p in (text or "").split("\n\n") if p.strip()]
        return Markup("".join(f"<p>{escape(p)}</p>" for p in parts))

    @app.template_filter("nicedate")
    def nicedate(value):
        try:
            return datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S").strftime("%d %b %Y, %H:%M")
        except Exception:
            return value or ""

    @app.template_filter("wa_number")
    def wa_number(value):
        digits = re.sub(r"\D", "", value or "")
        return "91" + digits if len(digits) == 10 else digits

    @app.template_filter("taglist")
    def taglist(value):
        return [t.strip() for t in (value or "").split(",") if t.strip()]

    @app.template_filter("youtube_embed")
    def youtube_embed(url):
        m = re.search(r"(?:youtu\.be/|v=|embed/)([A-Za-z0-9_-]{11})", url or "")
        return f"https://www.youtube.com/embed/{m.group(1)}" if m else ""


# ---------------------------------------------------------------- routes

def register_routes(app):
    def db():
        return app.get_db()

    def csrf_token():
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(16)
        return session["csrf"]

    @app.before_request
    def check_csrf():
        if request.method == "POST":
            token = session.get("csrf")
            if not token or token != request.form.get("csrf_token"):
                abort(400, "Your session expired. Please go back, refresh the page and try again.")

    @app.context_processor
    def inject_globals():
        s = get_settings(db())
        cats = db().execute("SELECT * FROM categories ORDER BY sort_order").fetchall()
        return dict(S=s, nav_categories=cats, csrf_token=csrf_token,
                    current_year=datetime.now().year, is_admin=bool(session.get("admin_id")),
                    site_url=app.config["SITE_URL"] or request.url_root.rstrip("/"))

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if request.path.startswith("/admin"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    def project_cards(where="", params=(), limit=None):
        sql = ("SELECT p.*, c.name AS category_name, "
               "(SELECT filename FROM project_images i WHERE i.project_id = p.id "
               " ORDER BY i.is_cover DESC, i.sort_order, i.id LIMIT 1) AS cover "
               "FROM projects p JOIN categories c ON c.slug = p.category "
               "WHERE p.published = 1 " + where + " ORDER BY p.sort_order, p.id")
        if limit:
            sql += f" LIMIT {int(limit)}"
        return db().execute(sql, params).fetchall()

    # ---------- public pages

    @app.route("/")
    def home():
        featured = project_cards("AND p.featured = 1", limit=6)
        services = db().execute("SELECT * FROM services ORDER BY sort_order LIMIT 6").fetchall()
        testimonials = db().execute(
            "SELECT * FROM testimonials WHERE published = 1 ORDER BY id DESC LIMIT 3").fetchall()
        total = db().execute("SELECT COUNT(*) FROM projects WHERE published = 1").fetchone()[0]
        n_services = db().execute("SELECT COUNT(*) FROM services").fetchone()[0]
        n_cats = db().execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        return render_template("home.html", featured=featured, services=services,
                               testimonials=testimonials, total=total,
                               n_services=n_services, n_cats=n_cats)

    @app.route("/about")
    def about():
        return render_template("about.html", approach=seed.APPROACH)

    @app.route("/services")
    def services():
        rows = db().execute("SELECT * FROM services ORDER BY sort_order").fetchall()
        return render_template("services.html", services=rows)

    @app.route("/projects")
    def projects():
        cat = request.args.get("category", "").strip()
        q = request.args.get("q", "").strip()
        where, params = "", []
        if cat:
            where += " AND p.category = ?"
            params.append(cat)
        if q:
            where += " AND (p.title LIKE ? OR p.location LIKE ? OR p.tags LIKE ? OR p.summary LIKE ?)"
            params += [f"%{q}%"] * 4
        rows = project_cards(where, tuple(params))
        counts = {r["category"]: r["n"] for r in db().execute(
            "SELECT category, COUNT(*) AS n FROM projects WHERE published = 1 GROUP BY category")}
        return render_template("projects.html", projects=rows, active=cat, q=q, counts=counts)

    @app.route("/projects/<slug>")
    def project_detail(slug):
        p = db().execute(
            "SELECT p.*, c.name AS category_name FROM projects p JOIN categories c ON c.slug = p.category "
            "WHERE p.slug = ? AND p.published = 1", (slug,)).fetchone()
        if not p:
            abort(404)
        images = db().execute(
            "SELECT * FROM project_images WHERE project_id = ? ORDER BY is_cover DESC, sort_order, id",
            (p["id"],)).fetchall()
        related = project_cards("AND p.category = ? AND p.id != ?", (p["category"], p["id"]), limit=3)
        return render_template("project_detail.html", p=p, images=images, related=related)

    @app.route("/testimonials")
    def testimonials():
        rows = db().execute("SELECT * FROM testimonials WHERE published = 1 ORDER BY id DESC").fetchall()
        return render_template("testimonials.html", testimonials=rows)

    @app.route("/contact", methods=["GET", "POST"])
    def contact():
        form = {"name": "", "phone": "", "email": "", "project_type": "", "message": ""}
        if request.method == "POST":
            form = {k: request.form.get(k, "").strip() for k in form}
            errors = []
            if request.form.get("website"):  # honeypot field, only bots fill it
                return redirect(url_for("contact_thanks"))
            if not form["name"]:
                errors.append("Please enter your name.")
            if not form["phone"] and not form["email"]:
                errors.append("Please give a phone number or an email so we can reply.")
            if form["email"] and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", form["email"]):
                errors.append("That email address does not look right.")
            if form["phone"] and len(re.sub(r"\D", "", form["phone"])) < 8:
                errors.append("That phone number looks too short.")
            if not form["message"]:
                errors.append("Please tell us a little about your project.")
            if len(form["message"]) > 3000:
                errors.append("Your message is too long. Please shorten it.")
            if not errors and too_many(("enq", request.remote_addr), 5, 3600):
                errors.append("You have sent several messages recently. Please call or WhatsApp us instead.")
            if errors:
                for e in errors:
                    flash(e, "error")
            else:
                cur = db().execute(
                    "INSERT INTO enquiries (name, phone, email, project_type, message) VALUES (?,?,?,?,?)",
                    (form["name"], form["phone"], form["email"], form["project_type"], form["message"]))
                db().commit()
                send_enquiry_email(app, form, get_settings(db()))
                return redirect(url_for("contact_thanks"))
        else:
            form["project_type"] = request.args.get("type", "")
            ref = request.args.get("project", "")
            if ref:
                form["message"] = f"I am interested in a project like: {ref}"
        return render_template("contact.html", form=form, project_types=PROJECT_TYPES)

    @app.route("/contact/thanks")
    def contact_thanks():
        return render_template("thanks.html")

    @app.route("/media/<path:filename>")
    def media(filename):
        resp = send_from_directory(app.config["UPLOAD_DIR"], filename, max_age=60 * 60 * 24 * 30)
        return resp

    @app.route("/robots.txt")
    def robots():
        base = app.config["SITE_URL"] or request.url_root.rstrip("/")
        return Response(f"User-agent: *\nDisallow: /admin\nSitemap: {base}/sitemap.xml\n", mimetype="text/plain")

    @app.route("/sitemap.xml")
    def sitemap():
        base = app.config["SITE_URL"] or request.url_root.rstrip("/")
        urls = ["/", "/about", "/services", "/projects", "/testimonials", "/contact"]
        urls += [f"/projects/{r['slug']}" for r in db().execute(
            "SELECT slug FROM projects WHERE published = 1")]
        xml = ('<?xml version="1.0" encoding="UTF-8"?>'
               '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
               + "".join(f"<url><loc>{base}{u}</loc></url>" for u in urls) + "</urlset>")
        return Response(xml, mimetype="application/xml")

    @app.errorhandler(404)
    def not_found(_e):
        return render_template("error.html", code=404, message="We could not find that page."), 404

    @app.errorhandler(400)
    def bad_request(e):
        return render_template("error.html", code=400, message=getattr(e, "description", "Bad request")), 400

    @app.errorhandler(413)
    def too_large(_e):
        return render_template("error.html", code=413,
                               message="That upload is too large. Please upload fewer photos at a time."), 413

    @app.errorhandler(500)
    def server_error(_e):
        return render_template("error.html", code=500, message="Something went wrong on our side."), 500

    # ---------- admin

    def login_required(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            if not session.get("admin_id"):
                return redirect(url_for("admin_login", next=request.path))
            return fn(*a, **kw)
        return wrapper

    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if request.method == "POST":
            key = ("login", request.remote_addr)
            if len(_hits.get(key, [])) >= 8 and time.time() - _hits[key][-1] < 600:
                flash("Too many attempts. Please wait a few minutes.", "error")
                return render_template("admin/login.html"), 429
            user = db().execute("SELECT * FROM admin_users WHERE username = ?",
                                (request.form.get("username", "").strip(),)).fetchone()
            if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
                _hits.pop(key, None)
                session.clear()
                session.permanent = True
                session["admin_id"] = user["id"]
                db().execute("UPDATE admin_users SET last_login = ? WHERE id = ?",
                             (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user["id"]))
                db().commit()
                nxt = request.args.get("next", "")
                return redirect(nxt if nxt.startswith("/admin") else url_for("admin_dashboard"))
            _hits.setdefault(key, []).append(time.time())
            flash("Wrong username or password.", "error")
        return render_template("admin/login.html")

    @app.route("/admin/logout", methods=["POST"])
    def admin_logout():
        session.clear()
        return redirect(url_for("admin_login"))

    @app.route("/admin")
    @login_required
    def admin_dashboard():
        stats = {
            "projects": db().execute("SELECT COUNT(*) FROM projects").fetchone()[0],
            "hidden": db().execute("SELECT COUNT(*) FROM projects WHERE published = 0").fetchone()[0],
            "new_enquiries": db().execute("SELECT COUNT(*) FROM enquiries WHERE status = 'new'").fetchone()[0],
            "enquiries": db().execute("SELECT COUNT(*) FROM enquiries").fetchone()[0],
            "no_photos": db().execute(
                "SELECT COUNT(*) FROM projects p WHERE NOT EXISTS "
                "(SELECT 1 FROM project_images i WHERE i.project_id = p.id)").fetchone()[0],
        }
        latest = db().execute("SELECT * FROM enquiries ORDER BY id DESC LIMIT 5").fetchall()
        return render_template("admin/dashboard.html", stats=stats, latest=latest)

    # --- projects
    @app.route("/admin/projects")
    @login_required
    def admin_projects():
        rows = db().execute(
            "SELECT p.*, c.name AS category_name, "
            "(SELECT COUNT(*) FROM project_images i WHERE i.project_id = p.id) AS photos "
            "FROM projects p JOIN categories c ON c.slug = p.category ORDER BY p.sort_order, p.id").fetchall()
        return render_template("admin/projects.html", projects=rows)

    def read_project_form():
        f = request.form
        data = {
            "title": f.get("title", "").strip(),
            "category": f.get("category", ""),
            "location": f.get("location", "").strip(),
            "area": f.get("area", "").strip(),
            "summary": f.get("summary", "").strip(),
            "description": f.get("description", "").strip(),
            "tags": ",".join(t.strip() for t in f.get("tags", "").split(",") if t.strip()),
            "studio_role": f.get("studio_role", "").strip(),
            "video_url": f.get("video_url", "").strip(),
            "featured": 1 if f.get("featured") else 0,
            "published": 1 if f.get("published") else 0,
        }
        errors = []
        if not data["title"]:
            errors.append("Please enter a project title.")
        valid = {r["slug"] for r in db().execute("SELECT slug FROM categories")}
        if data["category"] not in valid:
            errors.append("Please choose a category.")
        if data["video_url"] and not data["video_url"].startswith(("http://", "https://")):
            errors.append("The video link must start with http:// or https://")
        return data, errors

    @app.route("/admin/projects/new", methods=["GET", "POST"])
    @login_required
    def admin_project_new():
        cats = db().execute("SELECT * FROM categories ORDER BY sort_order").fetchall()
        data = {"title": "", "category": "", "location": "", "area": "", "summary": "", "description": "",
                "tags": "", "studio_role": "", "video_url": "", "featured": 0, "published": 1}
        if request.method == "POST":
            data, errors = read_project_form()
            if errors:
                for e in errors:
                    flash(e, "error")
            else:
                slug = unique_slug(db(), data["title"])
                nxt = db().execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM projects").fetchone()[0]
                cur = db().execute(
                    "INSERT INTO projects (slug, title, category, location, area, summary, description, tags,"
                    " studio_role, video_url, featured, published, sort_order) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (slug, data["title"], data["category"], data["location"], data["area"], data["summary"],
                     data["description"], data["tags"], data["studio_role"], data["video_url"],
                     data["featured"], data["published"], nxt))
                db().commit()
                flash("Project created. Now add photos below.", "ok")
                return redirect(url_for("admin_project_edit", pid=cur.lastrowid))
        return render_template("admin/project_form.html", p=data, cats=cats, images=[], is_new=True)

    @app.route("/admin/projects/<int:pid>", methods=["GET", "POST"])
    @login_required
    def admin_project_edit(pid):
        p = db().execute("SELECT * FROM projects WHERE id = ?", (pid,)).fetchone()
        if not p:
            abort(404)
        cats = db().execute("SELECT * FROM categories ORDER BY sort_order").fetchall()
        if request.method == "POST":
            data, errors = read_project_form()
            if errors:
                for e in errors:
                    flash(e, "error")
                data["id"], data["slug"] = pid, p["slug"]
                images = db().execute("SELECT * FROM project_images WHERE project_id = ? "
                                      "ORDER BY is_cover DESC, sort_order, id", (pid,)).fetchall()
                return render_template("admin/project_form.html", p=data, cats=cats, images=images, is_new=False)
            db().execute(
                "UPDATE projects SET title=?, category=?, location=?, area=?, summary=?, description=?, tags=?,"
                " studio_role=?, video_url=?, featured=?, published=? WHERE id=?",
                (data["title"], data["category"], data["location"], data["area"], data["summary"],
                 data["description"], data["tags"], data["studio_role"], data["video_url"],
                 data["featured"], data["published"], pid))
            db().commit()
            flash("Project saved.", "ok")
            return redirect(url_for("admin_project_edit", pid=pid))
        images = db().execute("SELECT * FROM project_images WHERE project_id = ? "
                              "ORDER BY is_cover DESC, sort_order, id", (pid,)).fetchall()
        return render_template("admin/project_form.html", p=p, cats=cats, images=images, is_new=False)

    @app.route("/admin/projects/<int:pid>/delete", methods=["POST"])
    @login_required
    def admin_project_delete(pid):
        imgs = db().execute("SELECT filename FROM project_images WHERE project_id = ?", (pid,)).fetchall()
        for i in imgs:
            remove_image_files(app.config["UPLOAD_DIR"], i["filename"])
        db().execute("DELETE FROM projects WHERE id = ?", (pid,))
        db().commit()
        flash("Project deleted.", "ok")
        return redirect(url_for("admin_projects"))

    @app.route("/admin/projects/<int:pid>/toggle/<field>", methods=["POST"])
    @login_required
    def admin_project_toggle(pid, field):
        if field not in ("featured", "published"):
            abort(404)
        db().execute(f"UPDATE projects SET {field} = 1 - {field} WHERE id = ?", (pid,))
        db().commit()
        return redirect(request.referrer or url_for("admin_projects"))

    @app.route("/admin/projects/<int:pid>/move/<direction>", methods=["POST"])
    @login_required
    def admin_project_move(pid, direction):
        rows = db().execute("SELECT id FROM projects ORDER BY sort_order, id").fetchall()
        ids = [r["id"] for r in rows]
        if pid in ids:
            i = ids.index(pid)
            j = i - 1 if direction == "up" else i + 1
            if 0 <= j < len(ids):
                ids[i], ids[j] = ids[j], ids[i]
                for pos, x in enumerate(ids):
                    db().execute("UPDATE projects SET sort_order = ? WHERE id = ?", (pos, x))
                db().commit()
        return redirect(url_for("admin_projects"))

    # --- project photos
    @app.route("/admin/projects/<int:pid>/photos", methods=["POST"])
    @login_required
    def admin_photos_upload(pid):
        if not db().execute("SELECT id FROM projects WHERE id = ?", (pid,)).fetchone():
            abort(404)
        files = [f for f in request.files.getlist("photos") if f and f.filename]
        saved, failed = 0, 0
        has_cover = db().execute("SELECT 1 FROM project_images WHERE project_id = ? AND is_cover = 1",
                                 (pid,)).fetchone()
        nxt = db().execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM project_images WHERE project_id = ?",
                           (pid,)).fetchone()[0]
        for f in files:
            base = save_image(f, app.config["UPLOAD_DIR"])
            if not base:
                failed += 1
                continue
            cover = 0 if has_cover else 1
            has_cover = True
            db().execute("INSERT INTO project_images (project_id, filename, sort_order, is_cover) VALUES (?,?,?,?)",
                         (pid, base, nxt, cover))
            nxt += 1
            saved += 1
        db().commit()
        if saved:
            flash(f"{saved} photo(s) uploaded.", "ok")
        if failed:
            flash(f"{failed} file(s) were skipped. Use JPG, PNG or WebP images.", "error")
        if not files:
            flash("Please choose at least one photo.", "error")
        return redirect(url_for("admin_project_edit", pid=pid) + "#photos")

    @app.route("/admin/photos/<int:iid>/<action>", methods=["POST"])
    @login_required
    def admin_photo_action(iid, action):
        img = db().execute("SELECT * FROM project_images WHERE id = ?", (iid,)).fetchone()
        if not img:
            abort(404)
        pid = img["project_id"]
        if action == "cover":
            db().execute("UPDATE project_images SET is_cover = 0 WHERE project_id = ?", (pid,))
            db().execute("UPDATE project_images SET is_cover = 1 WHERE id = ?", (iid,))
        elif action == "delete":
            remove_image_files(app.config["UPLOAD_DIR"], img["filename"])
            db().execute("DELETE FROM project_images WHERE id = ?", (iid,))
            if img["is_cover"]:
                first = db().execute("SELECT id FROM project_images WHERE project_id = ? "
                                     "ORDER BY sort_order, id LIMIT 1", (pid,)).fetchone()
                if first:
                    db().execute("UPDATE project_images SET is_cover = 1 WHERE id = ?", (first["id"],))
        elif action in ("up", "down"):
            rows = db().execute("SELECT id FROM project_images WHERE project_id = ? "
                                "ORDER BY sort_order, id", (pid,)).fetchall()
            ids = [r["id"] for r in rows]
            i = ids.index(iid)
            j = i - 1 if action == "up" else i + 1
            if 0 <= j < len(ids):
                ids[i], ids[j] = ids[j], ids[i]
                for pos, x in enumerate(ids):
                    db().execute("UPDATE project_images SET sort_order = ? WHERE id = ?", (pos, x))
        elif action == "caption":
            db().execute("UPDATE project_images SET caption = ? WHERE id = ?",
                         (request.form.get("caption", "").strip()[:200], iid))
        else:
            abort(404)
        db().commit()
        return redirect(url_for("admin_project_edit", pid=pid) + "#photos")

    # --- enquiries
    @app.route("/admin/enquiries")
    @login_required
    def admin_enquiries():
        status = request.args.get("status", "")
        if status in ENQUIRY_STATUSES:
            rows = db().execute("SELECT * FROM enquiries WHERE status = ? ORDER BY id DESC", (status,)).fetchall()
        else:
            rows = db().execute("SELECT * FROM enquiries ORDER BY id DESC").fetchall()
        return render_template("admin/enquiries.html", enquiries=rows, status=status, statuses=ENQUIRY_STATUSES)

    @app.route("/admin/enquiries/<int:eid>", methods=["POST"])
    @login_required
    def admin_enquiry_update(eid):
        status = request.form.get("status", "new")
        if status not in ENQUIRY_STATUSES:
            status = "new"
        db().execute("UPDATE enquiries SET status = ?, private_note = ? WHERE id = ?",
                     (status, request.form.get("private_note", "").strip()[:2000], eid))
        db().commit()
        flash("Enquiry updated.", "ok")
        return redirect(url_for("admin_enquiries", status=request.args.get("status", "")))

    @app.route("/admin/enquiries/<int:eid>/delete", methods=["POST"])
    @login_required
    def admin_enquiry_delete(eid):
        db().execute("DELETE FROM enquiries WHERE id = ?", (eid,))
        db().commit()
        flash("Enquiry deleted.", "ok")
        return redirect(url_for("admin_enquiries"))

    # --- services
    @app.route("/admin/services", methods=["GET", "POST"])
    @login_required
    def admin_services():
        if request.method == "POST":
            action = request.form.get("action")
            if action == "add":
                title = request.form.get("title", "").strip()
                if title:
                    nxt = db().execute("SELECT COALESCE(MAX(sort_order), 0) + 1 FROM services").fetchone()[0]
                    db().execute("INSERT INTO services (title, description, icon, sort_order) VALUES (?,?,?,?)",
                                 (title, request.form.get("description", "").strip(), "home", nxt))
                    flash("Service added.", "ok")
                else:
                    flash("Please enter a service name.", "error")
            elif action == "save":
                sid = int(request.form.get("id", 0))
                title = request.form.get("title", "").strip()
                if title:
                    db().execute("UPDATE services SET title = ?, description = ? WHERE id = ?",
                                 (title, request.form.get("description", "").strip(), sid))
                    flash("Service saved.", "ok")
                else:
                    flash("A service needs a name.", "error")
            elif action == "delete":
                db().execute("DELETE FROM services WHERE id = ?", (int(request.form.get("id", 0)),))
                flash("Service deleted.", "ok")
            db().commit()
            return redirect(url_for("admin_services"))
        rows = db().execute("SELECT * FROM services ORDER BY sort_order").fetchall()
        return render_template("admin/services.html", services=rows)

    # --- testimonials
    @app.route("/admin/testimonials", methods=["GET", "POST"])
    @login_required
    def admin_testimonials():
        if request.method == "POST":
            action = request.form.get("action")
            name = request.form.get("client_name", "").strip()
            quote = request.form.get("quote", "").strip()
            project = request.form.get("project_name", "").strip()
            if action == "add":
                if name and quote:
                    db().execute("INSERT INTO testimonials (client_name, project_name, quote) VALUES (?,?,?)",
                                 (name, project, quote))
                    flash("Testimonial added.", "ok")
                else:
                    flash("Please enter the client name and the quote.", "error")
            elif action == "save":
                if name and quote:
                    db().execute("UPDATE testimonials SET client_name=?, project_name=?, quote=?, published=? WHERE id=?",
                                 (name, project, quote, 1 if request.form.get("published") else 0,
                                  int(request.form.get("id", 0))))
                    flash("Testimonial saved.", "ok")
                else:
                    flash("A testimonial needs a name and a quote.", "error")
            elif action == "delete":
                db().execute("DELETE FROM testimonials WHERE id = ?", (int(request.form.get("id", 0)),))
                flash("Testimonial deleted.", "ok")
            db().commit()
            return redirect(url_for("admin_testimonials"))
        rows = db().execute("SELECT * FROM testimonials ORDER BY id DESC").fetchall()
        return render_template("admin/testimonials.html", testimonials=rows)

    # --- site text and contact details
    SETTING_FIELDS = [
        ("Home page", [("hero_headline", "Main headline", "text"), ("hero_sub", "Headline sub-text", "area"),
                       ("cta_text", "Main button text", "text")]),
        ("About page", [("about_title", "About heading", "text"), ("about_text", "About text", "area"),
                        ("founder_name", "Founder name", "text"), ("founder_role", "Founder title", "text"),
                        ("founder_text", "Founder text", "area")]),
        ("Eco-friendly section", [("eco_title", "Heading", "text"), ("eco_text", "Text", "area")]),
        ("Contact details", [("phone", "Phone number", "text"),
                             ("whatsapp", "WhatsApp number (with country code, digits only)", "text"),
                             ("email", "Email", "text"), ("address", "Address", "text"),
                             ("instagram", "Instagram username (without @)", "text")]),
    ]

    @app.route("/admin/site", methods=["GET", "POST"])
    @login_required
    def admin_site():
        if request.method == "POST":
            for _group, fields in SETTING_FIELDS:
                for key, _label, _kind in fields:
                    val = request.form.get(key, "").strip()
                    if key == "whatsapp":
                        val = re.sub(r"\D", "", val)
                    db().execute("INSERT INTO site_settings (key, value) VALUES (?, ?) "
                                 "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, val))
            db().commit()
            flash("Site text saved.", "ok")
            return redirect(url_for("admin_site"))
        return render_template("admin/site.html", groups=SETTING_FIELDS)

    @app.route("/admin/password", methods=["GET", "POST"])
    @login_required
    def admin_password():
        if request.method == "POST":
            user = db().execute("SELECT * FROM admin_users WHERE id = ?", (session["admin_id"],)).fetchone()
            cur, new, again = (request.form.get(k, "") for k in ("current", "new", "again"))
            if not check_password_hash(user["password_hash"], cur):
                flash("Your current password is not correct.", "error")
            elif len(new) < 8:
                flash("The new password must be at least 8 characters.", "error")
            elif new != again:
                flash("The two new passwords do not match.", "error")
            else:
                db().execute("UPDATE admin_users SET password_hash = ? WHERE id = ?",
                             (generate_password_hash(new), user["id"]))
                db().commit()
                flash("Password changed.", "ok")
                return redirect(url_for("admin_dashboard"))
        return render_template("admin/password.html")


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
