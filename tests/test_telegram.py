"""Tests for the Telegram Desktop JSON export importer."""
from __future__ import annotations
import json
from pathlib import Path
from pratibmb.importers.telegram import TelegramExport, _flatten_text


def test_flatten_text_plain_string():
    assert _flatten_text("hello world") == "hello world"


def test_flatten_text_entity_array():
    entities = [
        {"type": "plain", "text": "hello "},
        {"type": "bold", "text": "world"},
    ]
    assert _flatten_text(entities) == "hello world"


def test_flatten_text_mixed_array():
    """Array can contain bare strings alongside entity dicts."""
    entities = ["hello ", {"type": "link", "text": "example.com"}]
    assert _flatten_text(entities) == "hello example.com"


def _make_export(dir_: Path, chats: list[dict]):
    dir_.mkdir(parents=True, exist_ok=True)
    (dir_ / "result.json").write_text(json.dumps({
        "chats": {"list": chats},
    }))


def test_detect_valid(tmp_path: Path):
    _make_export(tmp_path, [])
    imp = TelegramExport()
    assert imp.detect(tmp_path)


def test_detect_missing_result(tmp_path: Path):
    imp = TelegramExport()
    assert not imp.detect(tmp_path)


def test_detect_no_chats_key(tmp_path: Path):
    (tmp_path / "result.json").write_text(json.dumps({"something": "else"}))
    imp = TelegramExport()
    assert not imp.detect(tmp_path)


def test_service_messages_skipped(tmp_path: Path):
    _make_export(tmp_path, [{
        "id": 1,
        "name": "Alice",
        "messages": [
            {"id": 1, "type": "message", "date_unixtime": "1600000000",
             "from": "Alice", "text": "hello"},
            {"id": 2, "type": "service", "date_unixtime": "1600000060",
             "from": "", "text": "Alice joined the group"},
            {"id": 3, "type": "message", "date_unixtime": "1600000120",
             "from": "Tapas", "text": "hi alice"},
        ],
    }])
    imp = TelegramExport()
    msgs = list(imp.load(tmp_path, self_name="Tapas"))
    assert len(msgs) == 2
    assert msgs[0].author == "other"
    assert msgs[0].text == "hello"
    assert msgs[1].author == "self"
    assert msgs[1].text == "hi alice"


def test_entity_array_text(tmp_path: Path):
    _make_export(tmp_path, [{
        "id": 1,
        "name": "Bob",
        "messages": [
            {"id": 1, "type": "message", "date_unixtime": "1600000000",
             "from": "Bob",
             "text": [{"type": "plain", "text": "check "}, {"type": "link", "text": "example.com"}]},
        ],
    }])
    imp = TelegramExport()
    msgs = list(imp.load(tmp_path, self_name="Tapas"))
    assert len(msgs) == 1
    assert msgs[0].text == "check example.com"


def test_multi_chat(tmp_path: Path):
    _make_export(tmp_path, [
        {
            "id": 100,
            "name": "Alice",
            "messages": [
                {"id": 1, "type": "message", "date_unixtime": "1600000000",
                 "from": "Alice", "text": "hey"},
            ],
        },
        {
            "id": 200,
            "name": "Work Group",
            "messages": [
                {"id": 1, "type": "message", "date_unixtime": "1600000060",
                 "from": "Tapas", "text": "morning"},
                {"id": 2, "type": "message", "date_unixtime": "1600000120",
                 "from": "Charlie", "text": "morning!"},
            ],
        },
    ])
    imp = TelegramExport()
    msgs = list(imp.load(tmp_path, self_name="Tapas"))
    assert len(msgs) == 3
    assert msgs[0].thread_id == "telegram::100"
    assert msgs[0].thread_name == "Alice"
    assert msgs[1].thread_id == "telegram::200"
    assert msgs[1].thread_name == "Work Group"
    assert msgs[1].author == "self"
    assert msgs[2].author == "other"
