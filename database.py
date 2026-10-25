import sqlite3
import os
from pathlib import Path
from config import Config

def get_db_connection():
    """Create and return a configured SQLite database connection."""
    # Ensure database directory exists
    db_path = Path(Config.DATABASE_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    # Enable foreign keys support in SQLite
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    """Initialize database tables and indexes."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Users Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Files Table with Foreign Key to Users
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        storage_key TEXT UNIQUE NOT NULL,
        file_size INTEGER NOT NULL,
        file_type TEXT NOT NULL,
        mime_type TEXT DEFAULT 'application/octet-stream',
        category TEXT DEFAULT 'others',
        storage_backend TEXT NOT NULL DEFAULT 'local',
        s3_bucket TEXT,
        uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
    );
    """)

    # Create indexes for fast querying and isolation checks
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_user ON files (user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_storage_key ON files (storage_key);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_category ON files (category);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", Config.DATABASE_PATH)
