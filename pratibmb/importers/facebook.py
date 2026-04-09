"""
Facebook "Download Your Information" (JSON format) importer.

Handles both:
  - Messenger threads  (your_activity_across_facebook/messages/inbox/<thread>/message_*.json)
  - Posts              (your_activity_across_facebook/posts/your_posts__check_ins__photos_and_videos_*.json)

Accepts either:
  - A path to the unzipped DYI root directory (we'll walk it)
  - A single message_*.json file
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from ..schema import Message


def _fix_mojibake(s: str) -> str:
    """Facebook DYI JSON double-encodes UTF-8 as latin-1. Undo it."""
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return s


def _ts(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


class FacebookDYI:
    name = "facebook_dyi"

    def detect(self, path: Path) -> bool:
        if path.is_file() and path.suffix == ".json":
            try:
                head = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                return False
            return isinstance(head, dict) and (
                "messages" in head or "participants" in head or "posts" in head
            )
        if path.is_dir():
            # Look for the known DYI folder markers
            markers = [
                "your_activity_across_facebook",
                "messages/inbox",
                "your_facebook_activity",
            ]
            for m in markers:
                if (path / m).exists():
                    return True
        return False

    def load(self, path: Path, self_name: str) -> Iterator[Message]:
        if path.is_file():
            yield from self._load_file(path, self_name)
            return
        # Walk messenger inbox
        for root in ("your_activity_across_facebook/messages/inbox",
                     "messages/inbox"):
            inbox = path / root
            if inbox.exists():
                for thread_dir in sorted(inbox.iterdir()):
                    if not thread_dir.is_dir():
                        continue
                    for mf in sorted(thread_dir.glob("message_*.json")):
                        yield from self._load_file(mf, self_name)
                break
        # Walk posts
        for root in ("your_activity_across_facebook/posts",
                     "posts"):
            posts = path / root
            if posts.exists():
                for pf in sorted(posts.glob("your_posts*.json")):
                    yield from self._load_posts(pf, self_name)
                break

    def _load_file(self, path: Path, self_name: str) -> Iterator[Message]:
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return
        if "messages" not in data:
            return
        title = _fix_mojibake(data.get("title", path.parent.name))
        participants = [
            _fix_mojibake(p.get("name", "")) for p in data.get("participants", [])
        ]
        thread_id = f"facebook_messenger::{title}"
        is_group = len(participants) > 2
        for m in data.get("messages", []):
            text = m.get("content")
            if not text:
                continue
            sender = _fix_mojibake(m.get("sender_name", ""))
            yield Message(
                source="facebook_messenger",
                timestamp=_ts(int(m.get("timestamp_ms", 0))),
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
            ts_raw = p.get("timestamp")
            if ts_raw is None:
                continue
            ts = datetime.fromtimestamp(int(ts_raw), tz=timezone.utc)
            text_bits: list[str] = []
            for d in p.get("data", []) or []:
                if "post" in d:
                    text_bits.append(d["post"])
            for att in p.get("attachments", []) or []:
                for a in att.get("data", []) or []:
                    if "text" in a:
                        text_bits.append(a["text"])
            text = _fix_mojibake(" ".join(b for b in text_bits if b).strip())
            if not text:
                continue
            yield Message(
                source="facebook_post",
                timestamp=ts,
                author="self",
                author_name=self_name,
                text=text,
                thread_id="facebook_post::self",
                thread_name="Facebook posts",
            )
