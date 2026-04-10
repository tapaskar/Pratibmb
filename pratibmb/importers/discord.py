"""
Discord importer for DiscordChatExporter JSON format.

Handles exports produced by DiscordChatExporter (https://github.com/Tyrrrz/DiscordChatExporter):
  - Single .json file with top-level "channel" and "messages" keys
  - Directory of .json files (one per channel)

Only "Default" message types are imported (joins, leaves, pins, etc. are skipped).
Guild name is stored in metadata when present (null for DMs).
"""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Iterator
from ..schema import Message


def _is_discord_export(data: dict) -> bool:
    """Return True if the parsed JSON looks like a DiscordChatExporter file."""
    return isinstance(data, dict) and "channel" in data and "messages" in data


class DiscordExport:
    name = "discord_export"

    def detect(self, path: Path) -> bool:
        if path.is_file() and path.suffix == ".json":
            try:
                data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                return False
            return _is_discord_export(data)
        if path.is_dir():
            for f in path.iterdir():
                if f.suffix == ".json":
                    try:
                        data = json.loads(f.read_text(encoding="utf-8", errors="replace"))
                    except Exception:
                        continue
                    if _is_discord_export(data):
                        return True
        return False

    def load(self, path: Path, self_name: str) -> Iterator[Message]:
        if path.is_file():
            yield from self._load_file(path, self_name)
            return
        for f in sorted(path.glob("*.json")):
            yield from self._load_file(f, self_name)

    def _load_file(self, path: Path, self_name: str) -> Iterator[Message]:
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return
        if not _is_discord_export(data):
            return

        channel = data.get("channel", {})
        channel_id = str(channel.get("id", ""))
        channel_name = channel.get("name", "")
        guild = data.get("guild", {})
        guild_name = guild.get("name") if guild else None

        thread_id = f"discord::{channel_id}"
        thread_name = channel_name

        meta: dict = {}
        if guild_name:
            meta["guild_name"] = guild_name

        for m in data.get("messages", []):
            if m.get("type") != "Default":
                continue
            text = m.get("content", "")
            author_info = m.get("author", {})
            author_name = author_info.get("name", "")
            ts_raw = m.get("timestamp")
            if not ts_raw:
                continue
            ts = datetime.fromisoformat(ts_raw)
            has_attachments = bool(m.get("attachments"))
            yield Message(
                source="discord",
                timestamp=ts,
                author="self" if author_name == self_name else "other",
                author_name=author_name or "unknown",
                text=text,
                thread_id=thread_id,
                thread_name=thread_name,
                media_ref="media" if has_attachments else None,
                metadata=dict(meta),
            )
