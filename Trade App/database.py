# file: database.py
import sqlite3
import os

DB_FILE = "user_data.db"

def init_db():
    """Initializes the database and creates the credentials table if it doesn't exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS credentials (
            id INTEGER PRIMARY KEY,
            client_id TEXT NOT NULL,
            access_token TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def save_credentials(client_id, access_token):
    """Saves or updates the user credentials in the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Use INSERT OR REPLACE to handle both new and existing entries
    cursor.execute('''
        INSERT OR REPLACE INTO credentials (id, client_id, access_token)
        VALUES (1, ?, ?)
    ''', (client_id, access_token))
    conn.commit()
    conn.close()

def get_credentials():
    """Retrieves user credentials from the database."""
    if not os.path.exists(DB_FILE):
        return None
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT client_id, access_token FROM credentials WHERE id = 1')
    creds = cursor.fetchone()
    conn.close()
    return creds if creds else None