"""Tests for the iMessage chat.db importer."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

from pratibmb.importers.imessage import IMessageDB, _apple_ts_to_datetime

# Apple epoch: 2001-01-01 UTC
_APPLE_EPOCH = datetime(2001, 1, 1, tzinfo=timezone.utc)


def _create_db(path: Path, messages: list[dict]) -> Path:
    """Create an in-memory-style chat.db on disk with the iMessage schema.

    Each message dict should have:
      text, date (Apple epoch int), is_from_me (0/1),
      handle_id_value (e.g. "+1234567890"),
      chat_identifier, display_name (optional).
    """
    db_path = path / "chat.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE handle (
            ROWID INTEGER PRIMARY KEY,
            id    TEXT NOT NULL
        );
        CREATE TABLE chat (
            ROWID           INTEGER PRIMARY KEY,
            chat_identifier TEXT NOT NULL,
            display_name    TEXT DEFAULT ''
        );
        CREATE TABLE message (
            ROWID           INTEGER PRIMARY KEY,
            text            TEXT,
            attributedBody  BLOB,
            date            INTEGER,
            is_from_me      INTEGER DEFAULT 0,
            handle_id       INTEGER
        );
        CREATE TABLE chat_message_join (
            chat_id    INTEGER,
            message_id INTEGER
        );
    """)

    # Collect unique handles and chats
    handles: dict[str, int] = {}
    chats: dict[str, int] = {}
    handle_counter = 0
    chat_counter = 0

    for m in messages:
        hid = m.get("handle_id_value", "+0000000000")
        if hid not in handles:
            handle_counter += 1
            handles[hid] = handle_counter
            conn.execute("INSERT INTO handle (ROWID, id) VALUES (?, ?)",
                         (handle_counter, hid))
        cid = m.get("chat_identifier", "chat0")
        if cid not in chats:
            chat_counter += 1
            chats[cid] = chat_counter
            conn.execute("INSERT INTO chat (ROWID, chat_identifier, display_name) VALUES (?, ?, ?)",
                         (chat_counter, cid, m.get("display_name", "")))

    for i, m in enumerate(messages, start=1):
        hid = m.get("handle_id_value", "+0000000000")
        handle_rowid = handles[hid]
        conn.execute(
            "INSERT INTO message (ROWID, text, attributedBody, date, is_from_me, handle_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (i, m.get("text"), m.get("attributedBody"), m["date"],
             m.get("is_from_me", 0), handle_rowid),
        )
        cid = m.get("chat_identifier", "chat0")
        conn.execute(
            "INSERT INTO chat_message_join (chat_id, message_id) VALUES (?, ?)",
            (chats[cid], i),
        )

    conn.commit()
    conn.close()
    return db_path


def test_basic_load(tmp_path: Path):
    # 2024-01-15 10:00:00 UTC in Apple nanoseconds
    ts_seconds = (datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc) - _APPLE_EPOCH).total_seconds()
    ts_nanos = int(ts_seconds * 1_000_000_000)

    db = _create_db(tmp_path, [
        {
            "text": "Hey!",
            "date": ts_nanos,
            "is_from_me": 1,
            "handle_id_value": "+1234567890",
            "chat_identifier": "iMessage;-;+1234567890",
            "display_name": "Sarah",
        },
        {
            "text": "Hi there",
            "date": ts_nanos + 60_000_000_000,  # +60s
            "is_from_me": 0,
            "handle_id_value": "+1234567890",
            "chat_identifier": "iMessage;-;+1234567890",
            "display_name": "Sarah",
        },
    ])
    imp = IMessageDB()
    assert imp.detect(db)
    msgs = list(imp.load(db, self_name="Tapas"))
    assert len(msgs) == 2
    assert msgs[0].author == "self"
    assert msgs[0].author_name == "Tapas"
    assert msgs[0].text == "Hey!"
    assert msgs[0].source == "imessage"
    assert msgs[0].thread_id == "imessage::iMessage;-;+1234567890"
    assert msgs[0].thread_name == "Sarah"
    assert msgs[1].author == "other"
    assert msgs[1].author_name == "+1234567890"


def test_apple_epoch_nanoseconds():
    """Nanosecond timestamps (> 1e15) are properly converted."""
    # 2024-01-01 00:00:00 UTC
    expected = datetime(2024, 1, 1, tzinfo=timezone.utc)
    delta = expected - _APPLE_EPOCH
    nanos = int(delta.total_seconds() * 1_000_000_000)
    assert nanos > 1_000_000_000_000_000  # confirm it's in nanos range
    result = _apple_ts_to_datetime(nanos)
    # Allow 1-second tolerance for float precision
    assert abs((result - expected).total_seconds()) < 1


def test_apple_epoch_seconds():
    """Second-resolution timestamps (< 1e15) are properly converted."""
    expected = datetime(2024, 1, 1, tzinfo=timezone.utc)
    secs = int((expected - _APPLE_EPOCH).total_seconds())
    assert secs < 1_000_000_000_000_000
    result = _apple_ts_to_datetime(secs)
    assert abs((result - expected).total_seconds()) < 1


def test_is_from_me_mapping(tmp_path: Path):
    ts_s = int((datetime(2024, 1, 1, tzinfo=timezone.utc) - _APPLE_EPOCH).total_seconds())
    ts_n = ts_s * 1_000_000_000
    db = _create_db(tmp_path, [
        {
            "text": "outgoing",
            "date": ts_n,
            "is_from_me": 1,
            "handle_id_value": "+9876543210",
            "chat_identifier": "chat1",
        },
        {
            "text": "incoming",
            "date": ts_n + 1_000_000_000,
            "is_from_me": 0,
            "handle_id_value": "+9876543210",
            "chat_identifier": "chat1",
        },
    ])
    msgs = list(IMessageDB().load(db, self_name="Me"))
    assert msgs[0].author == "self"
    assert msgs[0].author_name == "Me"
    assert msgs[1].author == "other"
    assert msgs[1].author_name == "+9876543210"


def test_detect_rejects_non_chatdb(tmp_path: Path):
    # Wrong filename
    wrong_name = tmp_path / "messages.db"
    conn = sqlite3.connect(str(wrong_name))
    conn.execute("CREATE TABLE message (ROWID INTEGER)")
    conn.close()
    assert IMessageDB().detect(wrong_name) is False

    # Right name, missing tables
    incomplete = tmp_path / "chat.db"
    conn = sqlite3.connect(str(incomplete))
    conn.execute("CREATE TABLE message (ROWID INTEGER)")
    conn.execute("CREATE TABLE handle (ROWID INTEGER)")
    # Missing chat and chat_message_join
    conn.close()
    assert IMessageDB().detect(incomplete) is False


def test_detect_accepts_valid_chatdb(tmp_path: Path):
    db = _create_db(tmp_path, [])  # empty but has all tables
    assert IMessageDB().detect(db) is True


def test_empty_text_skipped(tmp_path: Path):
    ts_s = int((datetime(2024, 6, 1, tzinfo=timezone.utc) - _APPLE_EPOCH).total_seconds())
    ts_n = ts_s * 1_000_000_000
    db = _create_db(tmp_path, [
        {
            "text": None,
            "date": ts_n,
            "is_from_me": 0,
            "handle_id_value": "+111",
            "chat_identifier": "c1",
        },
        {
            "text": "real message",
            "date": ts_n + 1_000_000_000,
            "is_from_me": 0,
            "handle_id_value": "+111",
            "chat_identifier": "c1",
        },
    ])
    msgs = list(IMessageDB().load(db, self_name="X"))
    assert len(msgs) == 1
    assert msgs[0].text == "real message"


def test_multiple_chats(tmp_path: Path):
    ts_s = int((datetime(2024, 3, 1, tzinfo=timezone.utc) - _APPLE_EPOCH).total_seconds())
    ts_n = ts_s * 1_000_000_000
    db = _create_db(tmp_path, [
        {
            "text": "msg to alice",
            "date": ts_n,
            "is_from_me": 1,
            "handle_id_value": "+1111",
            "chat_identifier": "iMessage;-;+1111",
            "display_name": "Alice",
        },
        {
            "text": "msg to bob",
            "date": ts_n + 1_000_000_000,
            "is_from_me": 1,
            "handle_id_value": "+2222",
            "chat_identifier": "iMessage;-;+2222",
            "display_name": "Bob",
        },
    ])
    msgs = list(IMessageDB().load(db, self_name="Me"))
    assert len(msgs) == 2
    thread_ids = {m.thread_id for m in msgs}
    assert len(thread_ids) == 2
    assert "imessage::iMessage;-;+1111" in thread_ids
    assert "imessage::iMessage;-;+2222" in thread_ids
