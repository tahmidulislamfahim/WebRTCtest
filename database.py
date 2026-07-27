import sqlite3
import hashlib
import uuid
import os
from typing import List, Optional, Dict

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webrtc.db")

def init_db():
    """Initialize SQLite database table for users."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def clear_all_users():
    """Deletes all users from the SQLite database."""
    init_db()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users")
    conn.commit()
    conn.close()

def _hash_password(password: str) -> str:
    """Hashes a password using SHA-256."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def register_user(username: str, password: str, display_name: str) -> Optional[Dict]:
    """Registers a new user in the database."""
    init_db()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Check if username already exists
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cursor.fetchone():
        conn.close()
        return None  # Username taken
    
    user_id = str(uuid.uuid4())[:8]  # Short 8-character unique ID
    password_hash = _hash_password(password)
    
    cursor.execute(
        "INSERT INTO users (id, username, password_hash, display_name) VALUES (?, ?, ?, ?)",
        (user_id, username, password_hash, display_name)
    )
    conn.commit()
    conn.close()
    
    return {
        "id": user_id,
        "username": username,
        "display_name": display_name
    }

def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """Authenticates a user by username and password."""
    init_db()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    password_hash = _hash_password(password)
    cursor.execute(
        "SELECT id, username, display_name FROM users WHERE username = ? AND password_hash = ?",
        (username, password_hash)
    )
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "id": row[0],
            "username": row[1],
            "display_name": row[2]
        }
    return None

def get_all_users() -> List[Dict]:
    """Retrieves all registered users."""
    init_db()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, display_name FROM users ORDER BY username ASC")
    rows = cursor.fetchall()
    conn.close()
    
    return [
        {
            "id": row[0],
            "username": row[1],
            "display_name": row[2]
        }
        for row in rows
    ]

# Initialize DB on module load
init_db()
