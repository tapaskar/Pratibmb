"""
Normalized message schema. Every importer must produce Message objects.
Keeping this tiny and source-agnostic is the whole point of the importer layer.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Literal, Any

Author = Literal["self", "other"]
Source = Literal[
    "whatsapp",
    "facebook_messenger",
    "facebook_post",
    "instagram_dm",
    "instagram_post",
    "gmail",
    "imessage",
    "telegram",
    "twitter",
    "discord",
    "generic",
]


@dataclass
class Message:
    """A single message/post, normalized across all sources."""
    source: Source
    timestamp: datetime
    author: Author
    author_name: str           # e.g. "Sarah", "self", "Mom"
    text: str
    thread_id: str             # chat/conversation id (stable across messages in same chat)
    thread_name: str = ""      # human-readable chat name ("Sarah", "Family", etc.)
    media_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def year(self) -> int:
        return self.timestamp.year

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["timestamp"] = self.timestamp.isoformat()
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Message":
        d = dict(d)
        d["timestamp"] = datetime.fromisoformat(d["timestamp"])
        return cls(**d)
