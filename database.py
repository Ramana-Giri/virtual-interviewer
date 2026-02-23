import sqlite3
import json
import hashlib
import secrets
from datetime import datetime

DB_NAME = "interview_db.sqlite"


def init_db():
    """Initializes the database with all required tables."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # 1. Users Table (New)
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            full_name TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 2. Sessions Table (Auth tokens - New)
    c.execute('''
        CREATE TABLE IF NOT EXISTS auth_sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            expires_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    # 3. Interview Session Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS interviews (
            session_id TEXT PRIMARY KEY,
            user_id INTEGER,
            candidate_name TEXT,
            target_role TEXT,
            start_time TEXT,
            status TEXT DEFAULT 'IN_PROGRESS',
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    ''')

    # 4. Responses Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            question_index INTEGER,
            question_text TEXT,
            transcript TEXT,
            audio_metrics TEXT,
            video_metrics TEXT,
            timeline_json TEXT,
            ai_feedback TEXT,
            ai_score INTEGER,
            FOREIGN KEY(session_id) REFERENCES interviews(session_id)
        )
    ''')

    conn.commit()
    conn.close()
    print(f"💽 Database initialized: {DB_NAME}")


# ─────────────────────────────────────────────
# AUTH FUNCTIONS
# ─────────────────────────────────────────────

def _hash_password(password: str, salt: str) -> str:
    """Hashes a password using SHA-256 with a salt."""
    return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()


def register_user(username: str, email: str, password: str, full_name: str = ""):
    """
    Creates a new user. Returns (True, user_id) on success or (False, error_message).
    """
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
        elif "email" in str(e):
            return False, "An account with this email already exists."
        return False, "Registration failed."
    finally:
        conn.close()


def login_user(username_or_email: str, password: str):
    """
    Validates credentials. Returns (True, token) on success or (False, error_message).
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Allow login with either username or email
    c.execute(
        "SELECT * FROM users WHERE username = ? OR email = ?",
        (username_or_email.lower().strip(), username_or_email.lower().strip())
    )
    user = c.fetchone()

    if not user:
        conn.close()
        return False, "Invalid username or password."

    # Verify password
    expected_hash = _hash_password(password, user["salt"])
    if expected_hash != user["password_hash"]:
        conn.close()
        return False, "Invalid username or password."

    # Create auth token (24-hour expiry)
    token = secrets.token_urlsafe(48)
    expires_at = datetime.now().replace(hour=23, minute=59, second=59).isoformat()
    c.execute(
        "INSERT INTO auth_sessions (token, user_id, expires_at) VALUES (?, ?, ?)",
        (token, user["id"], expires_at)
    )
    conn.commit()
    conn.close()
    return True, {"token": token, "user_id": user["id"], "full_name": user["full_name"], "username": user["username"]}


def validate_token(token: str):
    """
    Checks if a token is valid and not expired.
    Returns user_id if valid, None otherwise.
    """
    if not token:
        return None
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT user_id, expires_at FROM auth_sessions WHERE token = ?", (token,)
    )
    row = c.fetchone()
    conn.close()

    if not row:
        return None

    if datetime.fromisoformat(row["expires_at"]) < datetime.now():
        return None  # Token expired

    return row["user_id"]


def logout_user(token: str):
    """Deletes an auth token (logout)."""
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# INTERVIEW FUNCTIONS
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


def save_response(session_id, q_index, question, transcript, audio_metrics, video_metrics, timeline, ai_feedback, ai_score):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        INSERT INTO responses 
        (session_id, question_index, question_text, transcript, audio_metrics, video_metrics, timeline_json, ai_feedback, ai_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        session_id, q_index, question, transcript,
        json.dumps(audio_metrics), json.dumps(video_metrics),
        json.dumps(timeline), ai_feedback, ai_score
    ))
    conn.commit()
    conn.close()


def get_chat_history(session_id):
    """Returns a list of Q&A dicts for Gemini context."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT question_text as q_text, transcript, ai_score FROM responses WHERE session_id = ? ORDER BY question_index ASC",
        (session_id,)
    )
    rows = c.fetchall()
    conn.close()
    # FIX: original code had duplicate "role" key in dict — corrected here
    return [{"q_text": row["q_text"], "transcript": row["transcript"], "score": row["ai_score"]} for row in rows]


def get_full_report_data(session_id):
    """Fetches everything needed for the final report."""
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


def get_user_interviews(user_id):
    """Returns all past interviews for a user's dashboard."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute(
        "SELECT session_id, candidate_name, target_role, start_time, status FROM interviews WHERE user_id = ? ORDER BY start_time DESC",
        (user_id,)
    )
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows