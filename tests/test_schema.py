"""Tests for Message schema round-trip."""
from datetime import datetime, timezone
from pratibmb.schema import Message


def test_roundtrip():
    m = Message(
        source="whatsapp",
        timestamp=datetime(2022, 3, 12, 19, 45, 12, tzinfo=timezone.utc),
        author="self",
        author_name="Tapas",
        text="hey",
        thread_id="whatsapp::Sarah",
        thread_name="Sarah",
        metadata={"k": 1},
    )
    d = m.to_dict()
    m2 = Message.from_dict(d)
    assert m2.text == m.text
    assert m2.timestamp == m.timestamp
    assert m2.year == 2022
    assert m2.metadata == {"k": 1}
