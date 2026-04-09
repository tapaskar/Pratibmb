"""Tests for the SQLite store."""
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from pratibmb.schema import Message
from pratibmb.store import Store


def _msg(year: int, author: str, text: str) -> Message:
    return Message(
        source="whatsapp",
        timestamp=datetime(year, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
        author=author,
        author_name="Tapas" if author == "self" else "Sarah",
        text=text,
        thread_id="whatsapp::Sarah",
        thread_name="Sarah",
    )


def test_store_add_and_query(tmp_path: Path):
    s = Store(tmp_path / "c.db")
    try:
        s.add_messages([
            _msg(2020, "self", "hello"),
            _msg(2021, "other", "hi"),
            _msg(2022, "self", "bye"),
        ])
        assert s.count() == 3
        assert s.count(author="self") == 2
        assert s.count(year_max=2021) == 2
        assert s.count(year_max=2021, author="self") == 1
    finally:
        s.close()


def test_store_embeddings(tmp_path: Path):
    s = Store(tmp_path / "c.db")
    try:
        s.add_messages([_msg(2020, "self", "a"), _msg(2021, "self", "b")])
        chunks = list(s.iter_missing_embeddings(batch=100))
        assert len(chunks) == 1
        items = []
        for row in chunks[0]:
            v = np.ones(4, dtype=np.float32) * row["id"]
            items.append((row["id"], v))
        s.put_embeddings(items)
        ids, mat = s.load_embeddings(year_max=2021, author="self")
        assert mat.shape == (2, 4)
        assert len(ids) == 2
    finally:
        s.close()
