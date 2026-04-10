"""
iMessage macOS chat.db importer.

Reads the SQLite database that iMessage uses on macOS, typically located at
``~/Library/Messages/chat.db``.

Uses only ``sqlite3`` from stdlib — zero external dependencies.

Apple stores timestamps as nanoseconds since 2001-01-01 00:00:00 UTC (the
"Core Data" / "Cocoa" epoch). Older databases may use seconds instead; we
auto-detect by checking whether the value exceeds 1e15.
"""
from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Iterator

from ..schema import Message

# Apple epoch: 2001-01-01 00:00:00 UTC
_APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)

# Threshold to distinguish nanoseconds from seconds.
# A value > 1e15 is certainly nanoseconds (seconds would put us in year ~33M).
_NANO_THRESHOLD = 1_000_000_000_000_000

# Regex to extract readable text from attributedBody blobs (NSArchiver format).
# The UTF-8 text run sits after a specific marker in the plist binary.
_ATTRIBUTED_BODY_RE = re.compile(
    rb"(?:\x01\+|NSString).*?([^\x00-\x08\x0e-\x1f]{2,})"
)


def _apple_ts_to_datetime(ts: int | float) -> datetime:
    """Convert an Apple epoch timestamp (seconds or nanoseconds) to datetime."""
    if ts == 0:
        return _APPLE_EPOCH
    if ts > _NANO_THRESHOLD:
        ts = ts / 1_000_000_000
    return _APPLE_EPOCH + timedelta(seconds=ts)


def _extract_attributed_body(blob: bytes | None) -> str:
    """Try to extract plain text from an NSAttributedString blob."""
    if not blob:
        return ""
    # The actual text typically appears as a UTF-8 run after a
    # streamtyped / NSMutableAttributedString marker.
    m = _ATTRIBUTED_BODY_RE.search(blob)
    if m:
        try:
            return m.group(1).decode("utf-8", errors="replace").strip()
        except Exception:
            return ""
    return ""


_REQUIRED_TABLES = frozenset(["message", "handle", "chat", "chat_message_join"])

_QUERY = """\
SELECT
    m.ROWID,
    m.text,
    m.attributedBody,
    m.date,
    m.is_from_me,
    h.id          AS handle_id,
    c.chat_identifier,
    c.display_name
FROM message m
JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
JOIN chat c                ON c.ROWID = cmj.chat_id
LEFT JOIN handle h         ON h.ROWID = m.handle_id
ORDER BY m.date
"""


class IMessageDB:
    name = "imessage_db"

    def detect(self, path: Path) -> bool:
        if not path.is_file() or path.name != "chat.db":
            return False
        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = {row[0] for row in cur.fetchall()}
            conn.close()
            return _REQUIRED_TABLES.issubset(tables)
        except Exception:
            return False

    def load(self, path: Path, self_name: str) -> Iterator[Message]:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute(_QUERY)
            for row in cur:
                text = row["text"]
                if not text:
                    blob = row["attributedBody"]
                    text = _extract_attributed_body(blob) if blob else ""
                if not text:
                    continue

                ts_raw = row["date"]
                if ts_raw is None or ts_raw == 0:
                    continue
                ts = _apple_ts_to_datetime(ts_raw)

                is_from_me = bool(row["is_from_me"])
                handle_id = row["handle_id"] or ""
                chat_identifier = row["chat_identifier"] or ""
                display_name = row["display_name"] or ""

                author_name = self_name if is_from_me else (handle_id or "unknown")
                thread_name = display_name or handle_id or chat_identifier

                yield Message(
                    source="imessage",
                    timestamp=ts,
                    author="self" if is_from_me else "other",
                    author_name=author_name,
                    text=text,
                    thread_id=f"imessage::{chat_identifier}",
                    thread_name=thread_name,
                )
        finally:
            conn.close()
