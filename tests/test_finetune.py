"""Tests for the fine-tuning pipeline."""
from datetime import datetime, timezone, timedelta
from pathlib import Path

from pratibmb.schema import Message
from pratibmb.store import Store
from pratibmb.finetune.pairs import extract_pairs
from pratibmb.finetune.format import format_for_gemma, save_jsonl, split_dataset


def _msg(ts: datetime, author: str, name: str, text: str,
         thread_id: str = "fb::alice", thread_name: str = "Alice") -> Message:
    return Message(
        source="facebook_messenger",
        timestamp=ts,
        author=author,
        author_name=name,
        text=text,
        thread_id=thread_id,
        thread_name=thread_name,
    )


def _make_conversation(store: Store) -> None:
    """Insert a realistic conversation into the store."""
    base = datetime(2020, 3, 15, 10, 0, 0, tzinfo=timezone.utc)
    messages = [
        _msg(base, "other", "Alice", "Hey Tapas, how are you?"),
        _msg(base + timedelta(minutes=1), "self", "Tapas Kar",
             "I'm good! Just finished lunch."),
        _msg(base + timedelta(minutes=2), "other", "Alice",
             "Nice, what did you have?"),
        _msg(base + timedelta(minutes=3), "self", "Tapas Kar",
             "Made some dal and rice, classic comfort food"),
        _msg(base + timedelta(minutes=5), "other", "Alice",
             "That sounds great, I love dal"),
        _msg(base + timedelta(minutes=6), "self", "Tapas Kar",
             "Yeah me too, reminds me of home"),
        # A gap (different conversation next day)
        _msg(base + timedelta(days=1), "other", "Alice",
             "Did you watch the match last night?"),
        _msg(base + timedelta(days=1, minutes=2), "self", "Tapas Kar",
             "No I fell asleep early haha"),
    ]
    # Add a second thread
    base2 = datetime(2021, 6, 1, 14, 0, 0, tzinfo=timezone.utc)
    messages.extend([
        _msg(base2, "other", "Bob", "yo what's up",
             thread_id="fb::bob", thread_name="Bob"),
        _msg(base2 + timedelta(minutes=1), "self", "Tapas Kar",
             "not much, working from home today",
             thread_id="fb::bob", thread_name="Bob"),
    ])
    # Messages that should be filtered: too short, media, URL-only
    messages.extend([
        _msg(base + timedelta(hours=2), "other", "Alice", "ok"),
        _msg(base + timedelta(hours=2, minutes=1), "self", "Tapas Kar", "k"),
        _msg(base + timedelta(hours=3), "other", "Alice", "<media omitted>"),
        _msg(base + timedelta(hours=3, minutes=1), "self", "Tapas Kar",
             "That's a nice photo"),
        _msg(base + timedelta(hours=4), "other", "Alice",
             "https://youtube.com/watch?v=abc123"),
        _msg(base + timedelta(hours=4, minutes=1), "self", "Tapas Kar",
             "I'll check it out later"),
    ])
    store.add_messages(messages)


def test_extract_pairs(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    try:
        _make_conversation(store)
        pairs = extract_pairs(store, self_name="Tapas Kar")

        # Should have pairs from the natural other->self transitions
        assert len(pairs) >= 4  # at least the clean transitions
        assert len(pairs) <= 7  # not more than total transitions

        # Check structure
        for p in pairs:
            assert "context" in p
            assert "prompt" in p
            assert "completion" in p
            assert "thread_name" in p
            assert "timestamp" in p

        # Check that filtered messages are excluded
        completions = [p["completion"] for p in pairs]
        assert "k" not in completions  # too short
        prompts = [p["prompt"] for p in pairs]
        assert "<media omitted>" not in prompts
        assert "https://youtube.com/watch?v=abc123" not in prompts
    finally:
        store.close()


def test_extract_pairs_with_context(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    try:
        _make_conversation(store)
        pairs = extract_pairs(store, self_name="Tapas Kar", context_window=3)

        # The later pairs should have context from earlier messages
        pairs_with_ctx = [p for p in pairs if p["context"]]
        assert len(pairs_with_ctx) > 0
    finally:
        store.close()


def test_extract_pairs_max_pairs(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    try:
        _make_conversation(store)
        pairs = extract_pairs(store, self_name="Tapas Kar", max_pairs=2)
        assert len(pairs) == 2
    finally:
        store.close()


def test_format_for_gemma(tmp_path: Path):
    store = Store(tmp_path / "test.db")
    try:
        _make_conversation(store)
        pairs = extract_pairs(store, self_name="Tapas Kar")
        records = format_for_gemma(pairs)

        assert len(records) == len(pairs)
        for r in records:
            assert "text" in r
            assert "<start_of_turn>user" in r["text"]
            assert "<start_of_turn>model" in r["text"]
            assert "<end_of_turn>" in r["text"]
    finally:
        store.close()


def test_save_jsonl(tmp_path: Path):
    records = [
        {"text": "<start_of_turn>user\nhello<end_of_turn>\n<start_of_turn>model\nhi<end_of_turn>"},
        {"text": "<start_of_turn>user\nbye<end_of_turn>\n<start_of_turn>model\nsee ya<end_of_turn>"},
    ]
    out = tmp_path / "data" / "train.jsonl"
    count = save_jsonl(records, out)

    assert count == 2
    assert out.exists()

    import json
    lines = out.read_text().strip().split("\n")
    assert len(lines) == 2
    for line in lines:
        obj = json.loads(line)
        assert "text" in obj
        assert "<start_of_turn>" in obj["text"]


def test_split_dataset():
    records = [{"text": f"record_{i}"} for i in range(100)]
    train, val = split_dataset(records, train_ratio=0.9)
    assert len(train) == 90
    assert len(val) == 10


def test_extract_empty_db(tmp_path: Path):
    store = Store(tmp_path / "empty.db")
    try:
        pairs = extract_pairs(store, self_name="Nobody")
        assert pairs == []
    finally:
        store.close()
