# database.py
import sqlite3
import json
import time
from typing import Optional, List

DB_FILE = 'bonuslab.db'


def get_conn():
    conn = sqlite3.connect(DB_FILE, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel TEXT,
            orig_message_id INTEGER,
            text TEXT,
            media_paths TEXT,
            has_media INTEGER DEFAULT 0,
            has_video INTEGER DEFAULT 0,
            owner_message_ids TEXT,
            status TEXT DEFAULT 'pending',
            created_at INTEGER
        )
    ''')
    conn.commit()
    conn.close()


def post_exists(channel: str, orig_message_id: int) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM posts WHERE channel=? AND orig_message_id=?", (channel, orig_message_id))
    res = cur.fetchone()
    conn.close()
    return res is not None


def save_post(channel: str, orig_message_id: int, text: str, media_paths: Optional[List[str]], has_video: bool) -> int:
    conn = get_conn()
    cur = conn.cursor()
    media_json = json.dumps(media_paths or [])
    ts = int(time.time())
    cur.execute('''
        INSERT INTO posts (channel, orig_message_id, text, media_paths, has_media, has_video, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (channel, orig_message_id, text, media_json, 1 if media_paths else 0, int(has_video), ts))
    post_id = cur.lastrowid
    conn.commit()
    conn.close()
    return post_id


def update_media_paths(post_id: int, media_paths: List[str]):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE posts SET media_paths=?, has_media=? WHERE id=?",
        (json.dumps(media_paths), 1 if media_paths else 0, post_id)
    )
    conn.commit()
    conn.close()


def set_owner_message_ids(post_id: int, message_ids: List[int]):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "UPDATE posts SET owner_message_ids=? WHERE id=?",
        (json.dumps(message_ids), post_id)
    )
    conn.commit()
    conn.close()


def get_owner_message_ids(post_id: int) -> List[int]:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT owner_message_ids FROM posts WHERE id=?", (post_id,))
    row = cur.fetchone()
    conn.close()
    if not row or not row["owner_message_ids"]:
        return []
    try:
        return json.loads(row["owner_message_ids"])
    except Exception:
        return []


def update_status(post_id: int, status: str):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE posts SET status=? WHERE id=?", (status, post_id))
    conn.commit()
    conn.close()


def get_post(post_id: int):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM posts WHERE id=?", (post_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def list_pending(limit=50):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, channel, text, created_at FROM posts WHERE status='pending' ORDER BY created_at DESC LIMIT ?",
        (limit,)
    )
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]
