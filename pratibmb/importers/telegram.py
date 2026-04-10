"""
Telegram Desktop JSON export importer.

Handles the "result.json" produced by Telegram Desktop's "Export chat history"
feature. Each chat's messages are iterated; service messages are skipped.

The text field in Telegram exports can be either a plain string or an array of
entity objects like [{"type": "plain", "text": "hello"}, ...].  We flatten
both forms into a single string.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from ..schema import Message


def _flatten_text(raw: str | list) -> str:
    """Turn Telegram's text field into a plain string.

    Plain messages have ``"text": "hello"``.  Messages with formatting use an
    array of entity dicts: ``[{"type": "plain", "text": "hi "}, ...]``.
    """
    if isinstance(raw, str):
        return raw
    parts: list[str] = []
    for chunk in raw:
        if isinstance(chunk, str):
            parts.append(chunk)
        elif isinstance(chunk, dict):
            parts.append(chunk.get("text", ""))
    return "".join(parts)


class TelegramExport:
    name = "telegram_export"

    def detect(self, path: Path) -> bool:
        if not path.is_dir():
            return False
        result = path / "result.json"
        if not result.exists():
            return False
        try:
            with result.open("r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
            return isinstance(data, dict) and "chats" in data
        except Exception:
            return False

    def load(self, path: Path, self_name: str) -> Iterator[Message]:
        result = path / "result.json"
        with result.open("r", encoding="utf-8", errors="replace") as f:
            data = json.load(f)

        for chat in data.get("chats", {}).get("list", []):
            chat_id = str(chat.get("id", ""))
            chat_name = chat.get("name", "")
            thread_id = f"telegram::{chat_id}"

            for msg in chat.get("messages", []):
                if msg.get("type") != "message":
                    continue

                raw_text = msg.get("text", "")
                text = _flatten_text(raw_text)
                if not text:
                    continue

                # Timestamp: prefer date_unixtime, fall back to date string
                ts: datetime | None = None
                if "date_unixtime" in msg:
                    ts = datetime.fromtimestamp(
                        int(msg["date_unixtime"]), tz=timezone.utc,
                    )
                elif "date" in msg:
                    try:
                        ts = datetime.fromisoformat(msg["date"])
                    except ValueError:
                        continue
                if ts is None:
                    continue

                sender = msg.get("from", "")
                author = "self" if sender == self_name else "other"

                yield Message(
                    source="telegram",
                    timestamp=ts,
                    author=author,
                    author_name=sender or "unknown",
                    text=text,
                    thread_id=thread_id,
                    thread_name=chat_name,
                )
