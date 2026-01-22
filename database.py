import sqlite3
import json
from datetime import datetime

DB_NAME = "interview_db.sqlite"


def init_db():
    """Initializes the database with two tables: interviews and responses."""
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    # 1. The Interview Session Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS interviews (
            session_id TEXT PRIMARY KEY,
            candidate_name TEXT,
            target_role TEXT,
            start_time TEXT,
            status TEXT DEFAULT 'IN_PROGRESS'
        )
    ''')

    # 2. The Responses Table (Stores every Q&A interaction)
    # We store the heavy JSON metrics as text to keep it simple
    c.execute('''
        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            question_index INTEGER,
            question_text TEXT,
            transcript TEXT,

            -- Metrics (Stored as JSON strings for flexibility)
            audio_metrics TEXT,
            video_metrics TEXT,
            timeline_json TEXT, 

            -- AI Analysis
            ai_feedback TEXT,
            ai_score INTEGER,

            FOREIGN KEY(session_id) REFERENCES interviews(session_id)
        )
    ''')

    conn.commit()
    conn.close()
    print(f"💽 Database initialized: {DB_NAME}")


def create_session(session_id, name, role):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO interviews (session_id, candidate_name, target_role, start_time) VALUES (?, ?, ?, ?)",
              (session_id, name, role, datetime.now().isoformat()))
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
        session_id,
        q_index,
        question,
        transcript,
        json.dumps(audio_metrics),
        json.dumps(video_metrics),
        json.dumps(timeline),
        ai_feedback,
        ai_score
    ))
    conn.commit()
    conn.close()


def get_chat_history(session_id):
    """
    Retrieves the conversation history for Gemini context.
    Returns a list of dicts: [{'question': '...', 'answer': '...'}]
    """
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    c = conn.cursor()
    c.execute(
        "SELECT question_text, transcript, ai_score FROM responses WHERE session_id = ? ORDER BY question_index ASC",
        (session_id,))
    rows = c.fetchall()
    conn.close()

    history = []
    for row in rows:
        history.append({
            "role": "interviewer", "content": row['question_text'],
            "role": "candidate", "content": row['transcript']
        })
    return history


def get_full_report_data(session_id):
    """Fetches everything needed for the final report"""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Get Session Info
    c.execute("SELECT * FROM interviews WHERE session_id = ?", (session_id,))
    session = dict(c.fetchone())

    # Get All Responses
    c.execute("SELECT * FROM responses WHERE session_id = ? ORDER BY question_index ASC", (session_id,))
    responses = [dict(row) for row in c.fetchall()]

    conn.close()
    return session, responses