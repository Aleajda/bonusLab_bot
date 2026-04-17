# database.py
import sqlite3
import json
import time
import hashlib
from typing import Optional, List
from PIL import Image
import imagehash

DB_FILE = 'bonuslab.db'


def get_text_hash(text: str) -> str:
    """Получаем MD5 хэш нормализованного текста."""
    normalized = ' '.join(text.lower().split())
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()


def normalize_text(text: str) -> str:
    return ' '.join((text or '').lower().split())


def is_duplicate_post(text: str, similarity_threshold: float = 0.9) -> bool:
    """Проверяет, есть ли в базе пост с похожим текстом."""
    import difflib
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT text FROM posts WHERE status IN ('pending', 'published')")
    rows = cur.fetchall()
    conn.close()

    new_text = ' '.join(text.lower().split())
    for r in rows:
        old_text = ' '.join((r['text'] or '').lower().split())
        ratio = difflib.SequenceMatcher(None, new_text, old_text).ratio()
        if ratio >= similarity_threshold:
            return True
    return False


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
            image_hashes TEXT,              -- NEW
            has_media INTEGER DEFAULT 0,
            has_video INTEGER DEFAULT 0,
            owner_message_ids TEXT,
            status TEXT DEFAULT 'pending',
            created_at INTEGER
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
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

    # считаем хэши изображений
    image_hash_list = []
    if media_paths:
        for p in media_paths:
            h = calc_image_hash(p)
            if h:
                image_hash_list.append(h)

    media_json = json.dumps(media_paths or [])
    hashes_json = json.dumps(image_hash_list)

    ts = int(time.time())
    cur.execute('''
        INSERT INTO posts (channel, orig_message_id, text, media_paths, image_hashes, has_media, has_video, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (channel, orig_message_id, text, media_json, hashes_json,
          1 if media_paths else 0, int(has_video), ts))

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


def get_status_counts():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT status, COUNT(*) AS cnt
        FROM posts
        GROUP BY status
        """
    )
    rows = cur.fetchall()
    conn.close()
    counts = {"pending": 0, "published": 0, "rejected": 0, "error": 0}
    for row in rows:
        counts[row["status"]] = row["cnt"]
    return counts


def set_auto_mode(enabled: bool):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO settings(key, value)
        VALUES('auto_mode', ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value
        """,
        ("1" if enabled else "0",)
    )
    conn.commit()
    conn.close()


def get_auto_mode(default: bool = False) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT value FROM settings WHERE key='auto_mode'")
    row = cur.fetchone()
    conn.close()
    if not row:
        return bool(default)
    return str(row["value"]).strip() in ("1", "true", "True", "on", "yes")


def delete_post(post_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM posts WHERE id=?", (post_id,))
    conn.commit()
    conn.close()


def calc_image_hash(path: str) -> str:
    try:
        img = Image.open(path)
        return str(imagehash.phash(img))
    except Exception:
        return None


def is_similar_image_duplicate(new_paths, threshold=12) -> bool:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT image_hashes FROM posts WHERE image_hashes IS NOT NULL")
    rows = cur.fetchall()
    conn.close()

    # читаем хэши новых изображений
    new_hashes = []
    for p in new_paths:
        h = calc_image_hash(p)
        if h:
            new_hashes.append(imagehash.hex_to_hash(h))

    if not new_hashes:
        return False

    # сравниваем с существующими
    for row in rows:
        if not row["image_hashes"]:
            continue

        try:
            old_hashes = json.loads(row["image_hashes"])
        except:
            continue

        for oh in old_hashes:
            old_h = imagehash.hex_to_hash(oh)
            for nh in new_hashes:
                dist = old_h - nh
                if dist <= threshold:
                    print(f"[IMG DUP] расстояние = {dist}")
                    return True

    return False


def is_exact_duplicate_recent(text: str, within_seconds: int) -> bool:
    """Проверяет точный дубликат текста только в свежем окне времени."""
    new_text = normalize_text(text)
    if not new_text:
        return False

    since_ts = int(time.time()) - int(within_seconds)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT text
        FROM posts
        WHERE created_at >= ?
          AND status IN ('pending', 'published')
        """,
        (since_ts,)
    )
    rows = cur.fetchall()
    conn.close()

    for row in rows:
        if normalize_text(row["text"]) == new_text:
            return True
    return False


def is_similar_image_duplicate_recent(new_paths, threshold=12, within_seconds=10800) -> bool:
    """Проверяет дубликаты изображений только в свежем окне времени."""
    since_ts = int(time.time()) - int(within_seconds)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT image_hashes
        FROM posts
        WHERE image_hashes IS NOT NULL
          AND created_at >= ?
          AND status IN ('pending', 'published')
        """,
        (since_ts,)
    )
    rows = cur.fetchall()
    conn.close()

    new_hashes = []
    for p in new_paths:
        h = calc_image_hash(p)
        if h:
            new_hashes.append(imagehash.hex_to_hash(h))

    if not new_hashes:
        return False

    for row in rows:
        if not row["image_hashes"]:
            continue

        try:
            old_hashes = json.loads(row["image_hashes"])
        except Exception:
            continue

        for oh in old_hashes:
            old_h = imagehash.hex_to_hash(oh)
            for nh in new_hashes:
                dist = old_h - nh
                if dist <= threshold:
                    print(f"[IMG DUP RECENT] расстояние = {dist}")
                    return True

    return False
