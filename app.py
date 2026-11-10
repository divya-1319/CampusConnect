import os
import sqlite3
from flask import Flask, render_template, render_template_string
from flask import request, redirect, url_for, session
from jinja2 import FileSystemLoader

PROJECT_PATH = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PROJECT_PATH, "database", "campusconnect.db")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")

if not ADMIN_PASSWORD:
    raise RuntimeError("ADMIN_PASSWORD environment variable is required")

app = Flask(
    __name__,
    template_folder=os.path.join(PROJECT_PATH, "templates"),
    static_folder=os.path.join(PROJECT_PATH, "static")
)

app.secret_key = os.environ.get("FLASK_SECRET_KEY")

if not app.secret_key:
    raise RuntimeError("FLASK_SECRET_KEY environment variable is required")
app.jinja_loader = FileSystemLoader(os.path.join(PROJECT_PATH, "templates"))


@app.route("/")
def full_home():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT event_name, description, category FROM events")
    events = cursor.fetchall()
    conn.close()
    return render_template("index.html", events=events)


@app.route("/events")
def full_events():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events")
    events = cursor.fetchall()
    conn.close()
    return render_template("events.html", events=events)


@app.route("/register", methods=["POST"])
def full_register():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    event_name = request.form.get("event", "").strip()

    if not all([name, email, event_name]):
        return "Please fill all fields!"

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT event_id FROM events WHERE event_name=?",
        (event_name,)
    )
    event = cursor.fetchone()

    if not event:
        conn.close()
        return "Event not found!"

    cursor.execute(
        "SELECT student_id FROM students WHERE email=?",
        (email,)
    )
    student = cursor.fetchone()

    if student:
        student_id = student[0]
    else:
        cursor.execute("""
            INSERT INTO students (name, email, department)
            VALUES (?, ?, ?)
        """, (name, email, "Not Specified"))
        student_id = cursor.lastrowid

    try:
        cursor.execute("""
            INSERT INTO registrations
            (student_id, event_id, registration_date)
            VALUES (?, ?, DATE('now'))
        """, (student_id, event[0]))
        conn.commit()
        message = "Registration Successful!"
    except sqlite3.IntegrityError:
        message = "Already registered for this event!"

    conn.close()

    return render_template_string(
        "<h2>{{ message }}</h2><a href='/'>Go Home</a>",
        message=message
    )


@app.route("/login", methods=["GET", "POST"])
def full_login():
    if request.method == "POST":
        password = request.form.get("password", "")

        if password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("full_admin"))

        return "Invalid Password! <a href='/login'>Try Again</a>"

    return render_template("login.html")


@app.route("/admin")
def full_admin():
    if not session.get("admin_logged_in"):
        return redirect(url_for("full_login"))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM events")
    total_events = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM registrations")
    total_registrations = cursor.fetchone()[0]

    cursor.execute("""
        SELECT events.event_id, events.event_name,
               COUNT(registrations.registration_id)
        FROM events
        LEFT JOIN registrations
        ON events.event_id = registrations.event_id
        GROUP BY events.event_id, events.event_name
        ORDER BY events.event_id
    """)
    event_data = cursor.fetchall()
    conn.close()

    return render_template(
        "admin.html",
        total_events=total_events,
        total_students=total_students,
        total_registrations=total_registrations,
        event_data=event_data
    )


@app.route("/logout")
def full_logout():
    session.clear()
    return redirect(url_for("full_login"))


@app.route("/add-event", methods=["GET", "POST"])
def full_add_event():
    if not session.get("admin_logged_in"):
        return redirect(url_for("full_login"))

    if request.method == "POST":
        form = request.form
        event_name = form.get("event_name", "").strip()
        description = form.get("description", "").strip()
        event_date = form.get("event_date", "").strip()
        venue = form.get("venue", "").strip()
        category = form.get("category", "").strip()
        capacity_text = form.get("capacity", "").strip()

        if not all([
            event_name, description, event_date,
            venue, category, capacity_text
        ]):
            return "Please fill all fields!"

        try:
            capacity = int(capacity_text)
            if capacity <= 0:
                return "Capacity must be positive!"
        except ValueError:
            return "Enter a valid capacity!"

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO events
            (event_name, description, event_date, venue, category, capacity)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            event_name, description, event_date,
            venue, category, capacity
        ))
        conn.commit()
        conn.close()

        return "Event Added Successfully! <a href='/admin'>Go to Dashboard</a>"

    return render_template("add_event.html")


@app.route("/edit-event/<int:event_id>", methods=["GET", "POST"])
def full_edit_event(event_id):
    if not session.get("admin_logged_in"):
        return redirect(url_for("full_login"))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if request.method == "POST":
        form = request.form
        event_name = form.get("event_name", "").strip()
        description = form.get("description", "").strip()
        event_date = form.get("event_date", "").strip()
        venue = form.get("venue", "").strip()
        category = form.get("category", "").strip()
        capacity_text = form.get("capacity", "").strip()

        if not all([
            event_name, description, event_date,
            venue, category, capacity_text
        ]):
            conn.close()
            return "Please enter valid event details!"

        try:
            capacity = int(capacity_text)
            if capacity <= 0:
                conn.close()
                return "Capacity must be positive!"
        except ValueError:
            conn.close()
            return "Enter a valid capacity!"

        cursor.execute("""
            UPDATE events
            SET event_name=?, description=?, event_date=?,
                venue=?, category=?, capacity=?
            WHERE event_id=?
        """, (
            event_name, description, event_date,
            venue, category, capacity, event_id
        ))
        conn.commit()
        conn.close()

        return "Event Updated Successfully! <a href='/admin'>Go to Dashboard</a>"

    cursor.execute("SELECT * FROM events WHERE event_id=?", (event_id,))
    event = cursor.fetchone()
    conn.close()

    if event is None:
        return "Event not found!", 404

    return render_template("edit_event.html", event=event)


@app.route("/delete-event/<int:event_id>", methods=["GET", "POST"])
def full_delete_event(event_id):
    if not session.get("admin_logged_in"):
        return redirect(url_for("full_login"))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT event_name FROM events WHERE event_id=?",
        (event_id,)
    )
    event = cursor.fetchone()

    if event is None:
        conn.close()
        return "Event not found!", 404

    if request.method == "POST":
        cursor.execute(
            "DELETE FROM registrations WHERE event_id=?",
            (event_id,)
        )
        cursor.execute(
            "DELETE FROM events WHERE event_id=?",
            (event_id,)
        )
        conn.commit()
        conn.close()
        return "Event Deleted Successfully! <a href='/admin'>Dashboard</a>"

    conn.close()

    return f"""
        <h2>Delete Event: {event[0]}?</h2>
        <p>Are you sure you want to delete this event?</p>
        <form method="POST">
            <button type="submit">Yes, Delete Event</button>
        </form>
        <a href="/admin">Cancel</a>
    """
import os

import sqlite3
from flask import Flask, render_template, render_template_string
from flask import request, redirect, url_for, session
from jinja2 import FileSystemLoader

PROJECT_PATH = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PROJECT_PATH, "database", "campusconnect.db")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    conn.executescript("""
    CREATE TABLE IF NOT EXISTS students (
        student_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        department TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_name TEXT NOT NULL,
        description TEXT,
        event_date TEXT NOT NULL,
        venue TEXT NOT NULL,
        category TEXT NOT NULL,
        capacity INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS registrations (
        registration_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        event_id INTEGER NOT NULL,
        registration_date TEXT NOT NULL,
        UNIQUE(student_id, event_id),
        FOREIGN KEY(student_id) REFERENCES students(student_id),
        FOREIGN KEY(event_id) REFERENCES events(event_id)
    );
    """)
    event_count = conn.execute(
        "SELECT COUNT(*) FROM events"
    ).fetchone()[0]

    if event_count == 0:
        demo_events = [
            ("Tech Fest 2026", "Annual technical festival", "2026-11-20", "Main Auditorium", "Technical", 100),
            ("Cultural Night", "Annual cultural celebration", "2026-11-25", "College Ground", "Cultural", 200),
            ("Coding Competition", "Programming competition", "2026-12-02", "Computer Lab", "Technical", 50),
            ("Sports Meet", "Annual sports event", "2026-12-10", "Sports Ground", "Sports", 150),
            ("AI Workshop", "Introduction to Artificial Intelligence", "2026-12-15", "Seminar Hall", "Workshop", 80)
        ]

        conn.executemany("""
            INSERT INTO events
            (event_name, description, event_date, venue, category, capacity)
            VALUES (?, ?, ?, ?, ?, ?)
        """, demo_events)

    conn.commit()
    conn.close()


init_db()

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "change-this-demo-password")

app = Flask(
    __name__,
    template_folder=os.path.join(PROJECT_PATH, "templates"),
    static_folder=os.path.join(PROJECT_PATH, "static")
)

app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-demo-secret")
app.jinja_loader = FileSystemLoader(os.path.join(PROJECT_PATH, "templates"))


@app.route("/")
def full_home():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT event_name, description, category FROM events")
    events = cursor.fetchall()
    conn.close()
    return render_template("index.html", events=events)


@app.route("/events")
def full_events():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM events")
    events = cursor.fetchall()
    conn.close()
    return render_template("events.html", events=events)


@app.route("/register", methods=["POST"])
def full_register():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    event_name = request.form.get("event", "").strip()

    if not all([name, email, event_name]):
        return "Please fill all fields!"

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT event_id FROM events WHERE event_name=?",
        (event_name,)
    )
    event = cursor.fetchone()

    if not event:
        conn.close()
        return "Event not found!"

    cursor.execute(
        "SELECT student_id FROM students WHERE email=?",
        (email,)
    )
    student = cursor.fetchone()

    if student:
        student_id = student[0]
    else:
        cursor.execute("""
            INSERT INTO students (name, email, department)
            VALUES (?, ?, ?)
        """, (name, email, "Not Specified"))
        student_id = cursor.lastrowid

    try:
        cursor.execute("""
            INSERT INTO registrations
            (student_id, event_id, registration_date)
            VALUES (?, ?, DATE('now'))
        """, (student_id, event[0]))
        conn.commit()
        message = "Registration Successful!"
    except sqlite3.IntegrityError:
        message = "Already registered for this event!"

    conn.close()

    return render_template_string(
        "<h2>{{ message }}</h2><a href='/'>Go Home</a>",
        message=message
    )


@app.route("/login", methods=["GET", "POST"])
def full_login():
    if request.method == "POST":
        password = request.form.get("password", "")

        if password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("full_admin"))

        return "Invalid Password! <a href='/login'>Try Again</a>"

    return render_template("login.html")


@app.route("/admin")
def full_admin():
    if not session.get("admin_logged_in"):
        return redirect(url_for("full_login"))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM events")
    total_events = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM students")
    total_students = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM registrations")
    total_registrations = cursor.fetchone()[0]

    cursor.execute("""
        SELECT events.event_id, events.event_name,
               COUNT(registrations.registration_id)
        FROM events
        LEFT JOIN registrations
        ON events.event_id = registrations.event_id
        GROUP BY events.event_id, events.event_name
        ORDER BY events.event_id
    """)
    event_data = cursor.fetchall()
    conn.close()

    return render_template(
        "admin.html",
        total_events=total_events,
        total_students=total_students,
        total_registrations=total_registrations,
        event_data=event_data
    )


@app.route("/logout")
def full_logout():
    session.clear()
    return redirect(url_for("full_login"))


@app.route("/add-event", methods=["GET", "POST"])
def full_add_event():
    if not session.get("admin_logged_in"):
        return redirect(url_for("full_login"))

    if request.method == "POST":
        form = request.form
        event_name = form.get("event_name", "").strip()
        description = form.get("description", "").strip()
        event_date = form.get("event_date", "").strip()
        venue = form.get("venue", "").strip()
        category = form.get("category", "").strip()
        capacity_text = form.get("capacity", "").strip()

        if not all([
            event_name, description, event_date,
            venue, category, capacity_text
        ]):
            return "Please fill all fields!"

        try:
            capacity = int(capacity_text)
            if capacity <= 0:
                return "Capacity must be positive!"
        except ValueError:
            return "Enter a valid capacity!"

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO events
            (event_name, description, event_date, venue, category, capacity)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            event_name, description, event_date,
            venue, category, capacity
        ))
        conn.commit()
        conn.close()

        return "Event Added Successfully! <a href='/admin'>Go to Dashboard</a>"

    return render_template("add_event.html")


@app.route("/edit-event/<int:event_id>", methods=["GET", "POST"])
def full_edit_event(event_id):
    if not session.get("admin_logged_in"):
        return redirect(url_for("full_login"))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    if request.method == "POST":
        form = request.form
        event_name = form.get("event_name", "").strip()
        description = form.get("description", "").strip()
        event_date = form.get("event_date", "").strip()
        venue = form.get("venue", "").strip()
        category = form.get("category", "").strip()
        capacity_text = form.get("capacity", "").strip()

        if not all([
            event_name, description, event_date,
            venue, category, capacity_text
        ]):
            conn.close()
            return "Please enter valid event details!"

        try:
            capacity = int(capacity_text)
            if capacity <= 0:
                conn.close()
                return "Capacity must be positive!"
        except ValueError:
            conn.close()
            return "Enter a valid capacity!"

        cursor.execute("""
            UPDATE events
            SET event_name=?, description=?, event_date=?,
                venue=?, category=?, capacity=?
            WHERE event_id=?
        """, (
            event_name, description, event_date,
            venue, category, capacity, event_id
        ))
        conn.commit()
        conn.close()

        return "Event Updated Successfully! <a href='/admin'>Go to Dashboard</a>"

    cursor.execute("SELECT * FROM events WHERE event_id=?", (event_id,))
    event = cursor.fetchone()
    conn.close()

    if event is None:
        return "Event not found!", 404

    return render_template("edit_event.html", event=event)


@app.route("/delete-event/<int:event_id>", methods=["GET", "POST"])
def full_delete_event(event_id):
    if not session.get("admin_logged_in"):
        return redirect(url_for("full_login"))

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT event_name FROM events WHERE event_id=?",
        (event_id,)
    )
    event = cursor.fetchone()

    if event is None:
        conn.close()
        return "Event not found!", 404

    if request.method == "POST":
        cursor.execute(
            "DELETE FROM registrations WHERE event_id=?",
            (event_id,)
        )
        cursor.execute(
            "DELETE FROM events WHERE event_id=?",
            (event_id,)
        )
        conn.commit()
        conn.close()
        return "Event Deleted Successfully! <a href='/admin'>Dashboard</a>"

    conn.close()

    return f"""
        <h2>Delete Event: {event[0]}?</h2>
        <p>Are you sure you want to delete this event?</p>
        <form method="POST">
            <button type="submit">Yes, Delete Event</button>
        </form>
        <a href="/admin">Cancel</a>
    """

