"""
Gmail Google Takeout MBOX importer.

Handles:
  - A single .mbox file
  - A directory containing .mbox files (Google Takeout structure)

Threading is reconstructed from References / In-Reply-To headers using a
union-find structure so that all messages in a conversation share the same
thread_id regardless of reply depth.

Zero external dependencies — uses only ``mailbox`` and ``email`` from stdlib.
"""
from __future__ import annotations

import email
import email.header
import email.utils
import mailbox
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterator

from ..schema import Message

# ---- helpers ---------------------------------------------------------------

_SUBJECT_PREFIX = re.compile(
    r"^(Re|Fwd|FW|RE|Fw)\s*:\s*", re.IGNORECASE
)

_CALENDAR_TYPES = frozenset([
    "text/calendar",
    "application/ics",
])

_SKIP_CONTENT_TYPES = frozenset([
    "multipart/report",
    "message/delivery-status",
    "message/disposition-notification",
])


def _normalize_subject(subject: str) -> str:
    """Strip Re:/Fwd:/RE:/FW: prefixes recursively."""
    prev = None
    while prev != subject:
        prev = subject
        subject = _SUBJECT_PREFIX.sub("", subject).strip()
    return subject


class _HTMLStripper(HTMLParser):
    """Minimal HTML→text converter."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts)


def _strip_html(html: str) -> str:
    s = _HTMLStripper()
    s.feed(html)
    return s.get_text()


def _decode_header(raw: str | None) -> str:
    """Decode an RFC-2047 encoded header value."""
    if not raw:
        return ""
    parts = email.header.decode_header(raw)
    decoded: list[str] = []
    for data, charset in parts:
        if isinstance(data, bytes):
            decoded.append(data.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(data)
    return " ".join(decoded)


def _extract_email(from_header: str) -> str:
    """Pull the bare email address from a From header."""
    _, addr = email.utils.parseaddr(from_header)
    return addr.lower()


def _extract_display_name(from_header: str) -> str:
    """Pull the display name from a From header."""
    name, _ = email.utils.parseaddr(from_header)
    return name


def _parse_date(msg: email.message.Message) -> datetime | None:
    raw = msg.get("Date")
    if not raw:
        return None
    parsed = email.utils.parsedate_to_datetime(raw)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _extract_body(msg: email.message.Message) -> str:
    """Walk MIME parts and return the best text body."""
    plain_parts: list[str] = []
    html_parts: list[str] = []

    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct in _CALENDAR_TYPES or ct in _SKIP_CONTENT_TYPES:
                return ""
            if ct == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    plain_parts.append(payload.decode(charset, errors="replace"))
            elif ct == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html_parts.append(payload.decode(charset, errors="replace"))
    else:
        ct = msg.get_content_type()
        if ct in _CALENDAR_TYPES or ct in _SKIP_CONTENT_TYPES:
            return ""
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            text = payload.decode(charset, errors="replace")
            if ct == "text/html":
                html_parts.append(text)
            else:
                plain_parts.append(text)

    if plain_parts:
        return "\n".join(plain_parts).strip()
    if html_parts:
        return _strip_html("\n".join(html_parts)).strip()
    return ""


# ---- union-find for threading ---------------------------------------------

class _UnionFind:
    """Simple union-find to cluster message-ids into threads."""

    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self._parent.setdefault(x, x)
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[rb] = ra


def _message_ids_from_header(raw: str | None) -> list[str]:
    """Extract all <...> message-ids from a References/In-Reply-To header."""
    if not raw:
        return []
    return re.findall(r"<([^>]+)>", raw)


# ---- importer --------------------------------------------------------------

class GmailMbox:
    name = "gmail_mbox"

    def detect(self, path: Path) -> bool:
        if path.is_file() and path.suffix.lower() == ".mbox":
            return True
        if path.is_dir():
            return any(path.glob("**/*.mbox"))
        return False

    def load(self, path: Path, self_name: str) -> Iterator[Message]:
        mbox_files: list[Path] = []
        if path.is_file():
            mbox_files.append(path)
        else:
            mbox_files.extend(sorted(path.rglob("*.mbox")))

        for mbox_path in mbox_files:
            yield from self._load_mbox(mbox_path, self_name)

    def _load_mbox(self, path: Path, self_name: str) -> Iterator[Message]:
        # First pass: build thread map
        uf = _UnionFind()
        msg_subjects: dict[str, str] = {}  # message-id -> normalized subject

        mbox = mailbox.mbox(str(path))
        for key in mbox.keys():
            raw_msg = mbox.get(key)
            if raw_msg is None:
                continue
            mid = raw_msg.get("Message-ID", "")
            mid = mid.strip("<>").strip() if mid else ""
            if not mid:
                continue
            # Record subject
            subj = _decode_header(raw_msg.get("Subject"))
            msg_subjects[mid] = _normalize_subject(subj)
            # Union with references
            refs = _message_ids_from_header(raw_msg.get("References"))
            irt = _message_ids_from_header(raw_msg.get("In-Reply-To"))
            all_related = refs + irt
            for related_id in all_related:
                uf.union(mid, related_id)

        mbox.close()

        # Second pass: yield messages
        self_name_lower = self_name.lower()

        mbox = mailbox.mbox(str(path))
        for key in mbox.keys():
            raw_msg = mbox.get(key)
            if raw_msg is None:
                continue

            # Skip delivery notifications
            ct = raw_msg.get_content_type()
            if ct in _SKIP_CONTENT_TYPES:
                continue

            # Parse date
            ts = _parse_date(raw_msg)
            if ts is None:
                continue

            # Extract body
            body = _extract_body(raw_msg)
            if not body:
                continue

            # From / author detection
            from_raw = _decode_header(raw_msg.get("From"))
            from_email = _extract_email(from_raw)
            from_display = _extract_display_name(from_raw)
            is_self = (
                self_name_lower in from_display.lower()
                or self_name_lower in from_email
            )
            author_name = from_display or from_email or "unknown"

            # Thread ID
            mid = raw_msg.get("Message-ID", "")
            mid = mid.strip("<>").strip() if mid else ""
            if mid:
                thread_root = uf.find(mid)
            else:
                thread_root = f"no-id-{ts.isoformat()}"
            thread_id = f"gmail::{thread_root}"

            # Subject / thread name
            subj = _decode_header(raw_msg.get("Subject"))
            thread_name = _normalize_subject(subj) if subj else ""

            yield Message(
                source="gmail",
                timestamp=ts,
                author="self" if is_self else "other",
                author_name=author_name,
                text=body,
                thread_id=thread_id,
                thread_name=thread_name,
            )

        mbox.close()
