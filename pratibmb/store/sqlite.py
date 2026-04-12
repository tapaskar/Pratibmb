"""
SQLite store for normalized messages + their embeddings.

We keep the schema deliberately flat and portable. Embeddings are stored as
raw float32 BLOBs in a sibling table keyed by message rowid; we don't depend
on the sqlite-vec extension yet (adds a native build step). Brute-force
cosine over ~100k embeddings is still sub-100ms on M-series Macs.
"""
from __future__ import annotations
import sqlite3
import struct
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator
import numpy as np

from ..schema import Message

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source       TEXT    NOT NULL,
    timestamp    TEXT    NOT NULL,     -- ISO-8601
    year         INTEGER NOT NULL,
    author       TEXT    NOT NULL,     -- 'self' or 'other'
    author_name  TEXT    NOT NULL,
    text         TEXT    NOT NULL,
    thread_id    TEXT    NOT NULL,
    thread_name  TEXT    NOT NULL,
    media_ref    TEXT,
    metadata     TEXT                  -- JSON
);
CREATE INDEX IF NOT EXISTS idx_messages_year      ON messages(year);
CREATE INDEX IF NOT EXISTS idx_messages_thread    ON messages(thread_id);
CREATE INDEX IF NOT EXISTS idx_messages_author    ON messages(author);
CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);

CREATE TABLE IF NOT EXISTS embeddings (
    message_id INTEGER PRIMARY KEY REFERENCES messages(id) ON DELETE CASCADE,
    dim        INTEGER NOT NULL,
    vector     BLOB    NOT NULL         -- float32 little-endian
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profile (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL              -- JSON
);
"""


class Store:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Cursor]:
        self._lock.acquire()
        cur = self.conn.cursor()
        try:
            yield cur
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        finally:
            self._lock.release()

    # -- messages ---------------------------------------------------------

    def add_messages(self, messages: Iterable[Message]) -> int:
        import json
        rows = []
        for m in messages:
            rows.append((
                m.source,
                m.timestamp.isoformat(),
                m.timestamp.year,
                m.author,
                m.author_name,
                m.text,
                m.thread_id,
                m.thread_name,
                m.media_ref,
                json.dumps(m.metadata) if m.metadata else None,
            ))
        with self.tx() as cur:
            cur.executemany(
                """INSERT INTO messages
                   (source, timestamp, year, author, author_name, text,
                    thread_id, thread_name, media_ref, metadata)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
        return len(rows)

    def count(self, year_max: int | None = None, author: str | None = None) -> int:
        q = "SELECT COUNT(*) FROM messages WHERE 1=1"
        args: list = []
        if year_max is not None:
            q += " AND year <= ?"
            args.append(year_max)
        if author is not None:
            q += " AND author = ?"
            args.append(author)
        return self.conn.execute(q, args).fetchone()[0]

    def iter_self_messages(self, year_max: int | None = None) -> Iterator[sqlite3.Row]:
        q = "SELECT * FROM messages WHERE author = 'self'"
        args: list = []
        if year_max is not None:
            q += " AND year <= ?"
            args.append(year_max)
        q += " ORDER BY timestamp ASC"
        yield from self.conn.execute(q, args)

    def iter_missing_embeddings(self, batch: int = 500) -> Iterator[list[sqlite3.Row]]:
        q = """SELECT m.id, m.text FROM messages m
               LEFT JOIN embeddings e ON e.message_id = m.id
               WHERE e.message_id IS NULL AND m.text <> ''"""
        cur = self.conn.execute(q)
        chunk: list[sqlite3.Row] = []
        for row in cur:
            chunk.append(row)
            if len(chunk) >= batch:
                yield chunk
                chunk = []
        if chunk:
            yield chunk

    # -- embeddings -------------------------------------------------------

    def put_embeddings(self, items: Iterable[tuple[int, np.ndarray]]) -> None:
        rows = []
        for mid, vec in items:
            v = np.asarray(vec, dtype=np.float32).ravel()
            rows.append((int(mid), int(v.shape[0]), v.tobytes()))
        with self.tx() as cur:
            cur.executemany(
                "INSERT OR REPLACE INTO embeddings (message_id, dim, vector) VALUES (?, ?, ?)",
                rows,
            )

    def load_embeddings(self, year_max: int | None = None,
                        author: str = "self") -> tuple[list[int], np.ndarray]:
        q = """SELECT m.id, e.dim, e.vector
               FROM messages m
               JOIN embeddings e ON e.message_id = m.id
               WHERE m.author = ?"""
        args: list = [author]
        if year_max is not None:
            q += " AND m.year <= ?"
            args.append(year_max)
        ids: list[int] = []
        vecs: list[np.ndarray] = []
        for row in self.conn.execute(q, args):
            ids.append(row["id"])
            dim = row["dim"]
            vecs.append(np.frombuffer(row["vector"], dtype=np.float32, count=dim))
        if not vecs:
            return [], np.zeros((0, 0), dtype=np.float32)
        return ids, np.vstack(vecs)

    def get_messages(self, ids: list[int]) -> list[sqlite3.Row]:
        if not ids:
            return []
        placeholders = ",".join("?" * len(ids))
        return list(self.conn.execute(
            f"SELECT * FROM messages WHERE id IN ({placeholders})", ids
        ))

    # -- meta -------------------------------------------------------------

    def set_meta(self, key: str, value: str) -> None:
        with self.tx() as cur:
            cur.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                (key, value),
            )

    def get_meta(self, key: str) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM meta WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    # -- profile -------------------------------------------------------------

    def save_profile(self, key: str, data: str) -> None:
        """Store a profile JSON blob."""
        with self.tx() as cur:
            cur.execute(
                "INSERT OR REPLACE INTO profile (key, value) VALUES (?, ?)",
                (key, data),
            )

    def load_profile(self, key: str) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM profile WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    # -- thread context ------------------------------------------------------

    def get_thread_context(self, message_id: int, window: int = 3) -> dict:
        """Get a message with surrounding context from its thread.

        Returns dict with 'message' plus 'context_before' and 'context_after'
        lists (each up to `window` messages).
        """
        msg = self.conn.execute(
            "SELECT * FROM messages WHERE id = ?", (message_id,)
        ).fetchone()
        if msg is None:
            return {}
        tid = msg["thread_id"]
        ts = msg["timestamp"]

        before = list(self.conn.execute("""
            SELECT id, author_name, text, timestamp
            FROM messages
            WHERE thread_id = ? AND timestamp < ? AND text != ''
            ORDER BY timestamp DESC LIMIT ?
        """, (tid, ts, window)))
        before.reverse()

        after = list(self.conn.execute("""
            SELECT id, author_name, text, timestamp
            FROM messages
            WHERE thread_id = ? AND timestamp > ? AND text != ''
            ORDER BY timestamp ASC LIMIT ?
        """, (tid, ts, window)))

        return {
            "message": dict(msg),
            "context_before": [dict(r) for r in before],
            "context_after": [dict(r) for r in after],
        }

    def get_messages_enriched(self, ids: list[int],
                              thread_window: int = 3) -> list[dict]:
        """Get messages with thread context attached."""
        results = []
        for mid in ids:
            ctx = self.get_thread_context(mid, window=thread_window)
            if ctx:
                merged = ctx["message"]
                merged["context_before"] = ctx["context_before"]
                merged["context_after"] = ctx["context_after"]
                results.append(merged)
        return results

    # -- reset / delete ------------------------------------------------------

    def clear_embeddings(self) -> int:
        """Delete all embedding vectors. Returns count deleted."""
        count = self.conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0]
        with self.tx() as cur:
            cur.execute("DELETE FROM embeddings")
        return count

    def clear_profile(self) -> int:
        """Delete all extracted profile data. Returns count deleted."""
        count = self.conn.execute("SELECT COUNT(*) FROM profile").fetchone()[0]
        with self.tx() as cur:
            cur.execute("DELETE FROM profile")
        return count

    def clear_messages(self) -> int:
        """Delete all imported messages + their embeddings. Returns count deleted."""
        count = self.conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        with self.tx() as cur:
            cur.execute("DELETE FROM embeddings")
            cur.execute("DELETE FROM messages")
            cur.execute("DELETE FROM meta")
        return count

    def clear_all(self) -> dict:
        """Delete everything from the database. Returns counts per table."""
        counts = {
            "messages": self.conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0],
            "embeddings": self.conn.execute("SELECT COUNT(*) FROM embeddings").fetchone()[0],
            "profile": self.conn.execute("SELECT COUNT(*) FROM profile").fetchone()[0],
            "meta": self.conn.execute("SELECT COUNT(*) FROM meta").fetchone()[0],
        }
        with self.tx() as cur:
            cur.execute("DELETE FROM embeddings")
            cur.execute("DELETE FROM messages")
            cur.execute("DELETE FROM profile")
            cur.execute("DELETE FROM meta")
        # Reclaim disk space
        self.conn.execute("VACUUM")
        return counts
