"""
WhatsApp .txt exporter.

Handles the two common formats exported by "Export chat" on iOS/Android:

  [12/03/2022, 19:45:12] Sarah: hey you free tonight?
  12/03/2022, 19:45 - Sarah: hey you free tonight?

Multi-line messages, system lines, and "<Media omitted>" are handled.
Group chats use the chat file name as thread_name.
"""
from __future__ import annotations
import re
from datetime import datetime
from pathlib import Path
from typing import Iterator
from ..schema import Message

# Two bracket styles:
#   [dd/mm/yyyy, HH:MM:SS] Name: text
#   dd/mm/yyyy, HH:MM - Name: text
_LINE_BRACKET = re.compile(
    r"^\[(?P<d>\d{1,2}/\d{1,2}/\d{2,4}),\s*(?P<t>\d{1,2}:\d{2}(?::\d{2})?)\]\s*(?P<rest>.*)$"
)
_LINE_DASH = re.compile(
    r"^(?P<d>\d{1,2}/\d{1,2}/\d{2,4}),\s*(?P<t>\d{1,2}:\d{2}(?::\d{2})?)\s*-\s*(?P<rest>.*)$"
)

_SYSTEM_HINTS = (
    "Messages and calls are end-to-end encrypted",
    "created group",
    "added",
    "removed",
    "changed the subject",
    "changed this group's icon",
    "changed the group description",
    "You deleted this message",
    "This message was deleted",
)

_MEDIA_MARKERS = ("<Media omitted>", "image omitted", "video omitted",
                  "audio omitted", "sticker omitted", "document omitted",
                  "GIF omitted")


def _parse_ts(d: str, t: str) -> datetime | None:
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
                "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M",
                "%d/%m/%y %H:%M:%S", "%d/%m/%y %H:%M",
                "%m/%d/%y %H:%M:%S", "%m/%d/%y %H:%M"):
        try:
            return datetime.strptime(f"{d} {t}", fmt)
        except ValueError:
            continue
    return None


class WhatsAppTxt:
    name = "whatsapp_txt"

    def detect(self, path: Path) -> bool:
        if path.suffix.lower() != ".txt":
            return False
        try:
            with path.open("r", encoding="utf-8", errors="replace") as f:
                for i, line in enumerate(f):
                    if i > 20:
                        break
                    if _LINE_BRACKET.match(line) or _LINE_DASH.match(line):
                        return True
        except OSError:
            return False
        return False

    def load(self, path: Path, self_name: str) -> Iterator[Message]:
        thread_name = path.stem.replace("WhatsApp Chat with ", "").strip()
        thread_id = f"whatsapp::{thread_name}"

        current: dict | None = None

        def flush(cur: dict | None) -> Message | None:
            if not cur:
                return None
            text = "\n".join(cur["lines"]).strip()
            if not text:
                return None
            is_media = any(m in text for m in _MEDIA_MARKERS)
            return Message(
                source="whatsapp",
                timestamp=cur["ts"],
                author="self" if cur["name"] == self_name else "other",
                author_name=cur["name"],
                text="" if is_media else text,
                thread_id=thread_id,
                thread_name=thread_name,
                media_ref="media" if is_media else None,
            )

        with path.open("r", encoding="utf-8", errors="replace") as f:
            for raw in f:
                line = raw.rstrip("\n")
                m = _LINE_BRACKET.match(line) or _LINE_DASH.match(line)
                if m:
                    prev = flush(current)
                    if prev is not None and (prev.text or prev.media_ref):
                        yield prev
                    rest = m.group("rest")
                    ts = _parse_ts(m.group("d"), m.group("t"))
                    if ts is None:
                        current = None
                        continue
                    if ":" in rest:
                        name, _, body = rest.partition(":")
                        name = name.strip()
                        body = body.strip()
                    else:
                        # System message
                        if any(h in rest for h in _SYSTEM_HINTS):
                            current = None
                            continue
                        name, body = "system", rest.strip()
                    current = {"ts": ts, "name": name, "lines": [body]}
                else:
                    if current is not None:
                        current["lines"].append(line)

        last = flush(current)
        if last is not None and (last.text or last.media_ref):
            yield last
