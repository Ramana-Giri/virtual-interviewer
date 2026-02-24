import sqlite3
import json
import hashlib
import secrets
from datetime import datetime

DB_NAME = "interview_db.sqlite"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        full_name TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS auth_sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        expires_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS interviews (
        session_id TEXT PRIMARY KEY,
        user_id INTEGER,
        candidate_name TEXT,
        target_role TEXT,
        start_time TEXT,
        status TEXT DEFAULT 'IN_PROGRESS',
        FOREIGN KEY(user_id) REFERENCES users(id)
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        question_index INTEGER,
        question_text TEXT,
        question_type TEXT DEFAULT 'technical',
        transcript TEXT,
        audio_metrics TEXT,
        video_metrics TEXT,
        timeline_json TEXT,
        ai_feedback TEXT,
        ai_score INTEGER,
        FOREIGN KEY(session_id) REFERENCES interviews(session_id)
    )''')

    # ── Report cache table (NEW) ──
    # Stores the Gemini final report so it is never regenerated twice.
    c.execute('''CREATE TABLE IF NOT EXISTS reports (
        session_id TEXT PRIMARY KEY,
        report_json TEXT NOT NULL,
        generated_at TEXT NOT NULL,
        FOREIGN KEY(session_id) REFERENCES interviews(session_id)
    )''')

    conn.commit()

    # ── Migrate existing DBs that lack new columns ──
    _run_migrations(c)
    conn.commit()
    conn.close()
    print(f"💽 Database ready: {DB_NAME}")


def _run_migrations(c):
    """Safely adds columns/tables that may not exist in older DBs."""
    # user_id on interviews
    c.execute("PRAGMA table_info(interviews)")
    cols = [r[1] for r in c.fetchall()]
    if "user_id" not in cols:
        c.execute("ALTER TABLE interviews ADD COLUMN user_id INTEGER")
        print("  ↳ Migrated: interviews.user_id")

    # question_type on responses
    c.execute("PRAGMA table_info(responses)")
    cols = [r[1] for r in c.fetchall()]
    if "question_type" not in cols:
        c.execute("ALTER TABLE responses ADD COLUMN question_type TEXT DEFAULT 'technical'")
        print("  ↳ Migrated: responses.question_type")


# ─────────────────────────────────────────────
# AUTH
# ─────────────────────────────────────────────

def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


def register_user(username, email, password, full_name=""):
    salt = secrets.token_hex(32)
    password_hash = _hash_password(password, salt)
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO users (username, email, password_hash, salt, full_name) VALUES (?, ?, ?, ?, ?)",
            (username.lower().strip(), email.lower().strip(), password_hash, salt, full_name)
        )
        user_id = c.lastrowid
        conn.commit()
        return True, user_id
    except sqlite3.IntegrityError as e:
        if "username" in str(e):
            return False, "Username already taken."
        if "email" in str(e):
            return False, "An account with this email already exists."
        return False, "Registration failed."
    finally:
        conn.close()


def login_user(username_or_email, password):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT * FROM users WHERE username = ? OR email = ?",
        (username_or_email.lower().strip(), username_or_email.lower().strip())
    )
    user = c.fetchone()
    if not user:
        conn.close()
        return False, "Invalid username or password."
    if _hash_password(password, user["salt"]) != user["password_hash"]:
        conn.close()
        return False, "Invalid username or password."

    token = secrets.token_urlsafe(48)
    expires_at = datetime.now().replace(hour=23, minute=59, second=59).isoformat()
    c.execute(
        "INSERT INTO auth_sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user["id"], expires_at)
    )
    conn.commit()
    conn.close()
    return True, {
        "token": token,
        "user_id": user["id"],
        "full_name": user["full_name"],
        "username": user["username"]
    }


def validate_token(token):
    if not token:
        return None
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT user_id, expires_at FROM auth_sessions WHERE token = ?", (token,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    if datetime.fromisoformat(row["expires_at"]) < datetime.now():
        return None
    return row["user_id"]


def logout_user(token):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# INTERVIEWS
# ─────────────────────────────────────────────

def create_session(session_id, name, role, user_id=None):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT INTO interviews (session_id, user_id, candidate_name, target_role, start_time) VALUES (?, ?, ?, ?, ?)",
        (session_id, user_id, name, role, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def save_response(session_id, q_index, question, question_type, transcript,
                  audio_metrics, video_metrics, timeline, ai_feedback, ai_score):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT INTO responses
        (session_id, question_index, question_text, question_type, transcript,
         audio_metrics, video_metrics, timeline_json, ai_feedback, ai_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        session_id, q_index, question, question_type, transcript,
        json.dumps(audio_metrics), json.dumps(video_metrics),
        json.dumps(timeline), ai_feedback, ai_score
    ))
    conn.commit()
    conn.close()


def get_chat_history(session_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT question_text as q_text, transcript, ai_score FROM responses WHERE session_id = ? ORDER BY question_index ASC",
        (session_id,)
    )
    rows = c.fetchall()
    conn.close()
    return [{"q_text": row["q_text"], "transcript": row["transcript"], "score": row["ai_score"]} for row in rows]


def get_full_report_data(session_id):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM interviews WHERE session_id = ?", (session_id,))
    session_row = c.fetchone()
    if not session_row:
        conn.close()
        return None, []
    session = dict(session_row)
    c.execute("SELECT * FROM responses WHERE session_id = ? ORDER BY question_index ASC", (session_id,))
    responses = [dict(row) for row in c.fetchall()]
    conn.close()
    return session, responses


# ─────────────────────────────────────────────
# REPORT CACHE (NEW)
# ─────────────────────────────────────────────

def save_report(session_id: str, report_data: dict):
    """Persists the generated Gemini report so it is never regenerated."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO reports (session_id, report_json, generated_at) VALUES (?, ?, ?)",
        (session_id, json.dumps(report_data), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_cached_report(session_id: str):
    """Returns the cached report dict, or None if not yet generated."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT report_json FROM reports WHERE session_id = ?", (session_id,))
    row = c.fetchone()
    conn.close()
    if row:
        try:
            return json.loads(row["report_json"])
        except Exception:
            return None
    return None


# ─────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────

def get_user_interviews(user_id):
    """
    Returns only interviews with at least one submitted response.
    Also includes avg_score so the dashboard can display it.
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        """
        SELECT i.session_id, i.candidate_name, i.target_role, i.start_time, i.status,
               COUNT(r.id) as response_count,
               ROUND(AVG(r.ai_score), 1) as avg_score
        FROM interviews i
        LEFT JOIN responses r ON i.session_id = r.session_id
        WHERE i.user_id = ?
        GROUP BY i.session_id
        HAVING response_count > 0
        ORDER BY i.start_time DESC
        """,
        (user_id,)
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows