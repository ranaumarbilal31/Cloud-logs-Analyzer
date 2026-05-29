import os
import json
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

from mapreduce.engine import MapReduceEngine

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-in-production")
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {"log", "txt"}

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


# ─── Database ────────────────────────────────────────────────────────────────

def get_db():
    conn = psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(80) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role VARCHAR(20) DEFAULT 'admin',
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id SERIAL PRIMARY KEY,
            filename VARCHAR(255),
            uploaded_by VARCHAR(80),
            uploaded_at TIMESTAMP DEFAULT NOW(),
            total_lines INTEGER,
            results JSONB,
            duration_ms INTEGER
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id SERIAL PRIMARY KEY,
            username VARCHAR(80),
            action VARCHAR(255),
            ip_address VARCHAR(45),
            timestamp TIMESTAMP DEFAULT NOW()
        );
    """)
    # Seed default admin if not exists
    cur.execute("SELECT id FROM users WHERE username = 'admin'")
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
            ("admin", generate_password_hash("admin123"), "admin")
        )
    conn.commit()
    cur.close()
    conn.close()


# ─── Auth helpers ─────────────────────────────────────────────────────────────

def log_audit(username, action):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO audit_logs (username, action, ip_address) VALUES (%s, %s, %s)",
            (username, action, request.remote_addr)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception:
        pass


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cur.fetchone()
            cur.close()
            conn.close()
        except Exception as e:
            flash(f"Database error: {e}", "error")
            return render_template("login.html")

        if user and check_password_hash(user["password_hash"], password):
            session["user"] = username
            session["role"] = user["role"]
            log_audit(username, "LOGIN_SUCCESS")
            return redirect(url_for("dashboard"))
        else:
            log_audit(username, "LOGIN_FAILED")
            flash("Invalid credentials.", "error")
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    log_audit(session["user"], "LOGOUT")
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM analyses ORDER BY uploaded_at DESC LIMIT 10")
        analyses = list(cur.fetchall())
        cur.execute("SELECT COUNT(*) as cnt FROM analyses")
        total = cur.fetchone()["cnt"]
        cur.close()
        conn.close()
    except Exception:
        analyses, total = [], 0
    return render_template("dashboard.html", analyses=analyses, total=total, user=session["user"])


@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        if "logfile" not in request.files:
            flash("No file selected.", "error")
            return redirect(request.url)
        file = request.files["logfile"]
        if file.filename == "":
            flash("No file selected.", "error")
            return redirect(request.url)
        if not allowed_file(file.filename):
            flash("Only .log and .txt files are allowed.", "error")
            return redirect(request.url)

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(filepath)

        # Run MapReduce
        start = datetime.now()
        engine = MapReduceEngine(filepath)
        results = engine.run()
        elapsed = int((datetime.now() - start).total_seconds() * 1000)

        # Count lines
        with open(filepath, "r", errors="ignore") as f:
            total_lines = sum(1 for _ in f)

        # Persist to DB
        try:
            conn = get_db()
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO analyses (filename, uploaded_by, total_lines, results, duration_ms)
                   VALUES (%s, %s, %s, %s, %s) RETURNING id""",
                (filename, session["user"], total_lines, json.dumps(results), elapsed)
            )
            analysis_id = cur.fetchone()["id"]
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            flash(f"DB save error: {e}", "error")
            return redirect(url_for("dashboard"))

        log_audit(session["user"], f"UPLOAD:{filename}")
        return redirect(url_for("result", analysis_id=analysis_id))

    return render_template("upload.html", user=session["user"])


@app.route("/result/<int:analysis_id>")
@login_required
def result(analysis_id):
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM analyses WHERE id = %s", (analysis_id,))
        analysis = cur.fetchone()
        cur.close()
        conn.close()
    except Exception:
        analysis = None
    if not analysis:
        flash("Analysis not found.", "error")
        return redirect(url_for("dashboard"))
    return render_template("result.html", analysis=analysis, user=session["user"])


@app.route("/history")
@login_required
def history():
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM analyses ORDER BY uploaded_at DESC")
        analyses = list(cur.fetchall())
        cur.close()
        conn.close()
    except Exception:
        analyses = []
    return render_template("history.html", analyses=analyses, user=session["user"])


@app.route("/audit")
@login_required
def audit():
    if session.get("role") != "admin":
        flash("Access denied.", "error")
        return redirect(url_for("dashboard"))
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT 100")
        logs = list(cur.fetchall())
        cur.close()
        conn.close()
    except Exception:
        logs = []
    return render_template("audit.html", logs=logs, user=session["user"])


@app.route("/api/results/<int:analysis_id>")
@login_required
def api_results(analysis_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT results FROM analyses WHERE id = %s", (analysis_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row["results"])


if __name__ == "__main__":
    init_db()
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
