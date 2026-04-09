"""
Instagram "Download Your Information" JSON importer.

Covers:
  - DMs      (your_instagram_activity/messages/inbox/<thread>/message_*.json)
  - Posts    (your_instagram_activity/content/posts_*.json)

Like Facebook, Instagram DYI double-encodes UTF-8 as latin-1. We un-mojibake.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from ..schema import Message
from .facebook import _fix_mojibake


class InstagramDYI:
    name = "instagram_dyi"

    def detect(self, path: Path) -> bool:
        if path.is_dir():
            markers = [
                "your_instagram_activity",
                "messages/inbox",
                "content/posts_1.json",
            ]
            for m in markers:
                if (path / m).exists():
                    return True
        return False

    def load(self, path: Path, self_name: str) -> Iterator[Message]:
        for root in ("your_instagram_activity/messages/inbox",
                     "messages/inbox"):
            inbox = path / root
            if inbox.exists():
                for thread_dir in sorted(inbox.iterdir()):
                    if not thread_dir.is_dir():
                        continue
                    for mf in sorted(thread_dir.glob("message_*.json")):
                        yield from self._load_dm(mf, self_name)
                break

        for root in ("your_instagram_activity/content",
                     "content"):
            content = path / root
            if content.exists():
                for pf in sorted(content.glob("posts_*.json")):
                    yield from self._load_posts(pf, self_name)
                break

    def _load_dm(self, path: Path, self_name: str) -> Iterator[Message]:
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return
        title = _fix_mojibake(data.get("title", path.parent.name))
        thread_id = f"instagram_dm::{title}"
        is_group = len(data.get("participants", [])) > 2
        for m in data.get("messages", []):
            text = m.get("content")
            if not text:
                continue
            sender = _fix_mojibake(m.get("sender_name", ""))
            ts_ms = int(m.get("timestamp_ms", 0))
            yield Message(
                source="instagram_dm",
                timestamp=datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc),
                author="self" if sender == self_name else "other",
                author_name=sender or "unknown",
                text=_fix_mojibake(text),
                thread_id=thread_id,
                thread_name=title,
                metadata={"is_group": is_group},
            )

    def _load_posts(self, path: Path, self_name: str) -> Iterator[Message]:
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return
        posts = data if isinstance(data, list) else data.get("posts", [])
        for p in posts:
            ts = p.get("creation_timestamp") or p.get("taken_at")
            if ts is None:
                continue
            text_bits: list[str] = []
            for m_ in p.get("media", []) or []:
                title = m_.get("title")
                if title:
                    text_bits.append(title)
            top = p.get("title")
            if top:
                text_bits.append(top)
            text = _fix_mojibake(" ".join(text_bits).strip())
            if not text:
                continue
            yield Message(
                source="instagram_post",
                timestamp=datetime.fromtimestamp(int(ts), tz=timezone.utc),
                author="self",
                author_name=self_name,
                text=text,
                thread_id="instagram_post::self",
                thread_name="Instagram posts",
            )
