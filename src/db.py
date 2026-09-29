"""SQLite ledger: the source of truth for what exists, its sync state, and the activity log.
The vector shard only answers similarity search; everything you *display* comes from here."""
import sqlite3
import time
from contextlib import contextmanager

from config import DATA_DIR, DB_PATH


@contextmanager
def conn():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def init():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS memories(
            id INTEGER PRIMARY KEY,
            text TEXT NOT NULL,
            tags TEXT DEFAULT '',
            local_only INTEGER DEFAULT 0,
            reason TEXT DEFAULT '',
            sync_state TEXT NOT NULL,          -- pending | synced | local_only
            updated_ts REAL NOT NULL,
            synced_ts REAL DEFAULT 0,          -- updated_ts of the version last known to match the cloud
            device_id TEXT NOT NULL,
            deleted INTEGER DEFAULT 0          -- 1 = deleted locally, delete still to be pushed
        );
        CREATE TABLE IF NOT EXISTS activity(
            id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, kind TEXT, details TEXT);
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
        """)


# ---- meta / log -------------------------------------------------------------
def get_meta(key, default=None):
    with conn() as c:
        r = c.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return r["value"] if r else default


def set_meta(key, value):
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (key, str(value)))


def next_id() -> int:
    n = int(get_meta("next_id", 1))
    set_meta("next_id", n + 1)
    return n


def log(kind: str, details: str):
    with conn() as c:
        c.execute("INSERT INTO activity(ts, kind, details) VALUES(?,?,?)", (time.time(), kind, details))


def activity(limit=100):
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM activity ORDER BY id DESC LIMIT ?", (limit,))]


# ---- memories ---------------------------------------------------------------
def insert(mid, text, tags, local_only, reason, state, ts, device_id, synced_ts=0.0):
    with conn() as c:
        c.execute("""INSERT OR REPLACE INTO memories
            (id,text,tags,local_only,reason,sync_state,updated_ts,synced_ts,device_id,deleted)
            VALUES(?,?,?,?,?,?,?,?,?,0)""",
                  (mid, text, tags, int(local_only), reason, state, ts, synced_ts, device_id))


def get(mid):
    with conn() as c:
        r = c.execute("SELECT * FROM memories WHERE id=?", (mid,)).fetchone()
    return dict(r) if r else None


def all_memories():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM memories WHERE deleted=0 ORDER BY updated_ts DESC")]


def pending():
    with conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM memories WHERE sync_state='pending'")]


def count_pending() -> int:
    return len(pending())


def mark_deleted(mid):
    with conn() as c:
        c.execute("UPDATE memories SET deleted=1, sync_state='pending', updated_ts=? WHERE id=?", (time.time(), mid))


def hard_delete(mid):
    with conn() as c:
        c.execute("DELETE FROM memories WHERE id=?", (mid,))


def mark_synced(mid, ts):
    with conn() as c:
        c.execute("UPDATE memories SET sync_state='synced', synced_ts=? WHERE id=?", (ts, mid))
