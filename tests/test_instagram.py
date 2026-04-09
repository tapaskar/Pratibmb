"""Tests for the Instagram DYI importer."""
from __future__ import annotations
import json
from pathlib import Path
from pratibmb.importers.instagram import InstagramDYI


def test_instagram_dm(tmp_path: Path):
    inbox = tmp_path / "your_instagram_activity" / "messages" / "inbox"
    td = inbox / "sarah_xyz"
    td.mkdir(parents=True)
    (td / "message_1.json").write_text(json.dumps({
        "title": "sarah",
        "participants": [{"name": "tapas"}, {"name": "sarah"}],
        "messages": [
            {"sender_name": "tapas", "timestamp_ms": 1_650_000_000_000, "content": "hey"},
            {"sender_name": "sarah", "timestamp_ms": 1_650_000_060_000, "content": "yo"},
        ],
    }))
    imp = InstagramDYI()
    assert imp.detect(tmp_path)
    msgs = list(imp.load(tmp_path, self_name="tapas"))
    assert len(msgs) == 2
    assert msgs[0].source == "instagram_dm"
    assert msgs[0].author == "self"
    assert msgs[1].author == "other"
    assert msgs[0].year == 2022


def test_instagram_post(tmp_path: Path):
    content = tmp_path / "your_instagram_activity" / "content"
    content.mkdir(parents=True)
    (content / "posts_1.json").write_text(json.dumps([
        {
            "creation_timestamp": 1_650_000_000,
            "media": [{"title": "sunset in lisbon"}],
        }
    ]))
    imp = InstagramDYI()
    assert imp.detect(tmp_path)
    msgs = list(imp.load(tmp_path, self_name="tapas"))
    assert len(msgs) == 1
    assert msgs[0].source == "instagram_post"
    assert msgs[0].text == "sunset in lisbon"
    assert msgs[0].author == "self"
