"""Tests for the Facebook DYI importer."""
from __future__ import annotations
import json
from pathlib import Path
from pratibmb.importers.facebook import FacebookDYI, _fix_mojibake


def test_fix_mojibake():
    # "café" encoded once as utf-8 and then read as latin-1 (what FB does)
    raw = "café".encode("utf-8").decode("latin-1")
    assert _fix_mojibake(raw) == "café"


def _make_thread(dir_: Path, title: str, messages: list[dict]):
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / "message_1.json").write_text(json.dumps({
        "title": title,
        "participants": [{"name": "Tapas"}, {"name": "Sarah"}],
        "messages": messages,
    }))


def test_messenger_thread(tmp_path: Path):
    inbox = tmp_path / "your_activity_across_facebook" / "messages" / "inbox"
    thread_dir = inbox / "sarah_abc123"
    _make_thread(thread_dir, "Sarah", [
        {"sender_name": "Tapas", "timestamp_ms": 1_600_000_000_000, "content": "hey"},
        {"sender_name": "Sarah", "timestamp_ms": 1_600_000_060_000, "content": "hi there"},
        {"sender_name": "Tapas", "timestamp_ms": 1_600_000_120_000, "content": "all good?"},
    ])
    imp = FacebookDYI()
    assert imp.detect(tmp_path)
    msgs = list(imp.load(tmp_path, self_name="Tapas"))
    assert len(msgs) == 3
    assert msgs[0].author == "self"
    assert msgs[1].author == "other"
    assert msgs[1].author_name == "Sarah"
    assert msgs[0].source == "facebook_messenger"
    assert msgs[0].thread_name == "Sarah"
    assert msgs[0].thread_id == "facebook_messenger::Sarah"
    assert msgs[0].year == 2020


def test_direct_file_detection(tmp_path: Path):
    f = tmp_path / "message_1.json"
    f.write_text(json.dumps({
        "title": "Test",
        "participants": [{"name": "A"}, {"name": "B"}],
        "messages": [{"sender_name": "A", "timestamp_ms": 1_600_000_000_000, "content": "hey"}],
    }))
    imp = FacebookDYI()
    assert imp.detect(f)
    msgs = list(imp.load(f, self_name="A"))
    assert len(msgs) == 1
    assert msgs[0].text == "hey"
