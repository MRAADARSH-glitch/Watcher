import os
import sqlite3
import time
from datetime import timedelta
from functools import wraps

import cv2
from flask import (Flask, Response, flash, g, jsonify, redirect,
                   render_template, request, session)
from werkzeug.security import check_password_hash, generate_password_hash

from watcher import Watcher

app = Flask(__name__)
app.secret_key = "change-me-before-deploying"
app.permanent_session_lifetime = timedelta(days=30)  # stay logged in
watcher = Watcher()
watcher_user = None  # which user currently owns the camera
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "study.db")  # always next to app.py
DEFAULTS = {"away1": 5, "away2": 25, "check_eyes": 1, "break_every": 25, "break_len": 5}


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(e):
    if "db" in g:
        g.db.close()


def init_db():
    con = sqlite3.connect(DB)
    con.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY, username TEXT UNIQUE NOT NULL, hash TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS settings (
        user_id INTEGER PRIMARY KEY, away1 INTEGER, away2 INTEGER, check_eyes INTEGER,
        break_every INTEGER, break_len INTEGER);
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, started TEXT, duration INTEGER,
        focus INTEGER, away INTEGER, distractions INTEGER, breaks INTEGER);
    """)
    con.close()


def login_required(f):
    @wraps(f)
    def wrapper(*a, **k):
        if "user_id" not in session or not db().execute(
                "SELECT 1 FROM users WHERE id = ?", (session["user_id"],)).fetchone():
            session.clear()
            return redirect("/login")
        return f(*a, **k)
    return wrapper


def get_settings(uid):
    row = db().execute("SELECT * FROM settings WHERE user_id = ?", (uid,)).fetchone()
    return {k: row[k] for k in DEFAULTS} if row else dict(DEFAULTS)


@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name, pw = request.form.get("username", "").strip(), request.form.get("password", "")
        if not name or len(pw) < 4 or pw != request.form.get("confirm"):
            flash("Enter a username and matching password (4+ characters).")
            return render_template("register.html")
        try:
            cur = db().execute("INSERT INTO users (username, hash) VALUES (?, ?)",
                               (name, generate_password_hash(pw)))
            db().commit()
        except sqlite3.IntegrityError:
            flash("Username already taken.")
            return render_template("register.html")
        session.permanent = True
        session["user_id"], session["username"] = cur.lastrowid, name
        return redirect("/")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        row = db().execute("SELECT * FROM users WHERE username = ?",
                           (request.form.get("username", ""),)).fetchone()
        if row and check_password_hash(row["hash"], request.form.get("password", "")):
            session.permanent = True
            session["user_id"], session["username"] = row["id"], row["username"]
            return redirect("/")
        flash("Invalid username or password.")
    return render_template("login.html")


@app.route("/logout")
def logout():
    global watcher_user
    if watcher.running and watcher_user == session.get("user_id"):
        watcher.stop()
    session.clear()
    return redirect("/login")


@app.route("/start", methods=["POST"])
@login_required
def start():
    global watcher_user
    if watcher.running:
        return jsonify(ok=False, error="Camera is already in use."), 409
    watcher_user = session["user_id"]
    session["started"] = time.strftime("%Y-%m-%d %H:%M")
    session["t0"] = time.time()
    watcher.start(get_settings(watcher_user))
    return jsonify(ok=True)


@app.route("/stop", methods=["POST"])
@login_required
def stop():
    if not watcher.running or watcher_user != session["user_id"]:
        return jsonify(ok=False)
    st = watcher.status()
    watcher.stop()
    db().execute(
        "INSERT INTO sessions (user_id, started, duration, focus, away, distractions, breaks) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (session["user_id"], session.get("started"), int(time.time() - session.get("t0", time.time())),
         st["focus"], st["away"], st["distractions"], st["breaks"]))
    db().commit()
    return jsonify(ok=True)


@app.route("/status")
@login_required
def status():
    st = watcher.status()
    st["mine"] = watcher_user == session["user_id"]
    return jsonify(st)


@app.route("/video")
@login_required
def video():
    def frames():
        while watcher.running:
            f = watcher.frame
            if f is not None:
                ok, buf = cv2.imencode(".jpg", f)
                if ok:
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n"
            time.sleep(0.05)
    return Response(frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/camera")
@login_required
def camera():
    return render_template("camera.html")


@app.route("/history")
@login_required
def history():
    rows = db().execute("SELECT * FROM sessions WHERE user_id = ? ORDER BY id DESC",
                        (session["user_id"],)).fetchall()
    total = sum(r["focus"] for r in rows)
    return render_template("history.html", rows=rows, total=total)


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if request.method == "POST":
        try:
            v = [max(1, int(request.form[k])) for k in ("away1", "away2", "break_every", "break_len")]
        except (KeyError, ValueError):
            flash("Please enter valid numbers.")
            return redirect("/settings")
        if v[0] >= v[1]:
            flash("The second alert must be later than the first.")
            return redirect("/settings")
        db().execute("INSERT OR REPLACE INTO settings VALUES (?, ?, ?, ?, ?, ?)",
                     (session["user_id"], v[0], v[1], 1 if request.form.get("check_eyes") else 0, v[2], v[3]))
        db().commit()
        flash("Settings saved. They apply to your next session.")
        return redirect("/settings")
    return render_template("settings.html", s=get_settings(session["user_id"]))


@app.template_filter("hms")
def hms(sec):
    sec = int(sec or 0)
    return f"{sec // 3600}h {sec % 3600 // 60}m {sec % 60}s"


if __name__ == "__main__":
    init_db()
    app.run(debug=False, threaded=True)
