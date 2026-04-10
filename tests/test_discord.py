"""Tests for the Discord (DiscordChatExporter JSON) importer."""
from __future__ import annotations
import json
from pathlib import Path
from pratibmb.importers.discord import DiscordExport


SAMPLE_EXPORT = {
    "guild": {"id": "111", "name": "Test Server"},
    "channel": {"id": "222", "name": "general"},
    "messages": [
        {
            "id": "1",
            "type": "Default",
            "timestamp": "2024-06-15T10:30:00+00:00",
            "content": "hello everyone",
            "author": {"id": "10", "name": "Tapas"},
            "attachments": [],
        },
        {
            "id": "2",
            "type": "Default",
            "timestamp": "2024-06-15T10:31:00+00:00",
            "content": "hey Tapas!",
            "author": {"id": "20", "name": "Alice"},
            "attachments": [],
        },
        {
            "id": "3",
            "type": "ChannelJoin",
            "timestamp": "2024-06-15T10:32:00+00:00",
            "content": "",
            "author": {"id": "30", "name": "Bob"},
            "attachments": [],
        },
        {
            "id": "4",
            "type": "Default",
            "timestamp": "2024-06-15T10:33:00+00:00",
            "content": "check this out",
            "author": {"id": "20", "name": "Alice"},
            "attachments": [{"id": "a1", "url": "https://example.com/img.png"}],
        },
        {
            "id": "5",
            "type": "ChannelPinnedMessage",
            "timestamp": "2024-06-15T10:34:00+00:00",
            "content": "",
            "author": {"id": "10", "name": "Tapas"},
            "attachments": [],
        },
    ],
}

DM_EXPORT = {
    "guild": {},
    "channel": {"id": "333", "name": "Direct Message"},
    "messages": [
        {
            "id": "10",
            "type": "Default",
            "timestamp": "2024-07-01T08:00:00+00:00",
            "content": "dm test",
            "author": {"id": "10", "name": "Tapas"},
            "attachments": [],
        },
    ],
}

SECOND_CHANNEL = {
    "guild": {"id": "111", "name": "Test Server"},
    "channel": {"id": "444", "name": "random"},
    "messages": [
        {
            "id": "20",
            "type": "Default",
            "timestamp": "2024-06-16T12:00:00+00:00",
            "content": "random stuff",
            "author": {"id": "20", "name": "Alice"},
            "attachments": [],
        },
    ],
}


def _write_json(tmp_path: Path, name: str, data: dict) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_self_other_detection(tmp_path: Path):
    p = _write_json(tmp_path, "general.json", SAMPLE_EXPORT)
    imp = DiscordExport()
    msgs = list(imp.load(p, self_name="Tapas"))
    # Only Default messages (3 out of 5)
    assert len(msgs) == 3
    assert msgs[0].author == "self"
    assert msgs[0].author_name == "Tapas"
    assert msgs[1].author == "other"
    assert msgs[1].author_name == "Alice"


def test_filter_non_default_types(tmp_path: Path):
    p = _write_json(tmp_path, "general.json", SAMPLE_EXPORT)
    imp = DiscordExport()
    msgs = list(imp.load(p, self_name="Tapas"))
    types_present = {m.text for m in msgs}
    assert "hello everyone" in types_present
    assert "hey Tapas!" in types_present
    assert "check this out" in types_present
    # ChannelJoin and ChannelPinnedMessage must be skipped
    assert len(msgs) == 3


def test_attachments_set_media_ref(tmp_path: Path):
    p = _write_json(tmp_path, "general.json", SAMPLE_EXPORT)
    msgs = list(DiscordExport().load(p, self_name="Tapas"))
    assert msgs[0].media_ref is None
    assert msgs[2].media_ref == "media"


def test_thread_id_and_name(tmp_path: Path):
    p = _write_json(tmp_path, "general.json", SAMPLE_EXPORT)
    msgs = list(DiscordExport().load(p, self_name="Tapas"))
    assert all(m.thread_id == "discord::222" for m in msgs)
    assert all(m.thread_name == "general" for m in msgs)
    assert all(m.source == "discord" for m in msgs)


def test_guild_in_metadata(tmp_path: Path):
    p = _write_json(tmp_path, "general.json", SAMPLE_EXPORT)
    msgs = list(DiscordExport().load(p, self_name="Tapas"))
    assert msgs[0].metadata.get("guild_name") == "Test Server"


def test_dm_no_guild_in_metadata(tmp_path: Path):
    p = _write_json(tmp_path, "dm.json", DM_EXPORT)
    msgs = list(DiscordExport().load(p, self_name="Tapas"))
    assert len(msgs) == 1
    assert "guild_name" not in msgs[0].metadata


def test_directory_scan_multiple_channels(tmp_path: Path):
    _write_json(tmp_path, "general.json", SAMPLE_EXPORT)
    _write_json(tmp_path, "random.json", SECOND_CHANNEL)
    imp = DiscordExport()
    assert imp.detect(tmp_path)
    msgs = list(imp.load(tmp_path, self_name="Tapas"))
    thread_ids = {m.thread_id for m in msgs}
    assert "discord::222" in thread_ids
    assert "discord::444" in thread_ids
    assert len(msgs) == 4  # 3 from general + 1 from random


def test_detect_accepts_valid_file(tmp_path: Path):
    p = _write_json(tmp_path, "export.json", SAMPLE_EXPORT)
    assert DiscordExport().detect(p) is True


def test_detect_rejects_random_json(tmp_path: Path):
    p = _write_json(tmp_path, "other.json", {"users": [1, 2, 3]})
    assert DiscordExport().detect(p) is False


def test_detect_rejects_facebook_json(tmp_path: Path):
    p = _write_json(tmp_path, "fb.json", {"messages": [], "participants": []})
    assert DiscordExport().detect(p) is False


def test_detect_directory(tmp_path: Path):
    _write_json(tmp_path, "general.json", SAMPLE_EXPORT)
    assert DiscordExport().detect(tmp_path) is True


def test_detect_directory_no_match(tmp_path: Path):
    _write_json(tmp_path, "notes.json", {"notes": ["a", "b"]})
    assert DiscordExport().detect(tmp_path) is False


def test_timestamp_parsed_correctly(tmp_path: Path):
    p = _write_json(tmp_path, "general.json", SAMPLE_EXPORT)
    msgs = list(DiscordExport().load(p, self_name="Tapas"))
    assert msgs[0].timestamp.year == 2024
    assert msgs[0].timestamp.month == 6
    assert msgs[0].timestamp.day == 15
    assert msgs[0].timestamp.hour == 10
    assert msgs[0].timestamp.minute == 30
