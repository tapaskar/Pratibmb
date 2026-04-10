"""
Extract training pairs from the message corpus.

A training pair is a (context, prompt, completion) triple where:
  - context: 2-3 prior messages providing conversational context
  - prompt: the last "other" message (what someone said to you)
  - completion: your reply (the next "self" message)

We look for natural turn-taking: other -> self transitions within the
same thread, filtering out noise (empty, media-only, system messages).
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..store.sqlite import Store


# Messages matching these patterns are noise
_SKIP_PATTERNS = re.compile(
    r"^("
    r"<media omitted>|"
    r"\[media\]|"
    r"<image omitted>|"
    r"<video omitted>|"
    r"<audio omitted>|"
    r"<sticker omitted>|"
    r"<Contact card omitted>|"
    r"<document omitted>|"
    r"You sent a photo\.|"
    r"You sent a video\.|"
    r"You sent a sticker\.|"
    r"sent a photo\.|"
    r"sent a link\.|"
    r"Missed voice call|"
    r"Missed video call|"
    r"This message was deleted|"
    r"Messages and calls are end-to-end encrypted"
    r")$",
    re.IGNORECASE,
)

# System message authors (Facebook)
_SYSTEM_AUTHORS = {"facebook", "instagram", "system"}

# Minimum text length for a useful message
_MIN_TEXT_LEN = 3

# Maximum text length — very long messages are unusual for casual chat
_MAX_TEXT_LEN = 1000

# Maximum time gap (seconds) between prompt and completion to be
# considered part of the same conversational exchange
_MAX_GAP_SECONDS = 3600  # 1 hour


def _is_usable(text: str, author_name: str) -> bool:
    """Return True if a message is usable for training."""
    if not text or len(text.strip()) < _MIN_TEXT_LEN:
        return False
    if len(text) > _MAX_TEXT_LEN:
        return False
    if _SKIP_PATTERNS.match(text.strip()):
        return False
    if author_name.lower() in _SYSTEM_AUTHORS:
        return False
    # Skip URLs-only messages
    stripped = text.strip()
    if re.match(r"^https?://\S+$", stripped):
        return False
    return True


def _format_context_messages(messages: list[dict]) -> str:
    """Format a list of context messages into a readable block."""
    if not messages:
        return ""
    parts = []
    for m in messages:
        name = m["author_name"]
        text = m["text"].strip()
        parts.append(f"{name}: {text}")
    return "\n".join(parts)


def extract_pairs(
    store: "Store",
    self_name: str,
    max_pairs: int = 3000,
    context_window: int = 3,
    max_gap_seconds: int = _MAX_GAP_SECONDS,
) -> list[dict]:
    """Extract conversational training pairs from the corpus.

    Scans all threads for other->self turn transitions. For each,
    captures preceding context messages.

    Args:
        store: The SQLite message store.
        self_name: The user's display name (for labelling).
        max_pairs: Maximum number of pairs to extract.
        context_window: Number of prior messages to include as context.
        max_gap_seconds: Max seconds between prompt and completion.

    Returns:
        List of dicts with keys: context, prompt, completion,
        thread_name, prompt_author, timestamp.
    """
    from datetime import datetime

    pairs: list[dict] = []
    seen_completions: set[str] = set()

    # Fetch all threads
    threads = store.conn.execute(
        "SELECT DISTINCT thread_id FROM messages ORDER BY thread_id"
    ).fetchall()

    for thread_row in threads:
        thread_id = thread_row[0]

        # Get all messages in this thread ordered by time
        rows = store.conn.execute(
            """SELECT id, author, author_name, text, timestamp, thread_name
               FROM messages
               WHERE thread_id = ?
               ORDER BY timestamp ASC""",
            (thread_id,),
        ).fetchall()

        if len(rows) < 2:
            continue

        # Scan for other -> self transitions
        for i in range(1, len(rows)):
            prev = rows[i - 1]
            curr = rows[i]

            # We want: previous message is "other", current is "self"
            if prev["author"] != "other" or curr["author"] != "self":
                continue

            prompt_text = prev["text"].strip()
            completion_text = curr["text"].strip()

            # Filter unusable messages
            if not _is_usable(prompt_text, prev["author_name"]):
                continue
            if not _is_usable(completion_text, curr["author_name"]):
                continue

            # Check time gap
            try:
                t_prompt = datetime.fromisoformat(prev["timestamp"])
                t_completion = datetime.fromisoformat(curr["timestamp"])
                gap = (t_completion - t_prompt).total_seconds()
                if gap > max_gap_seconds or gap < 0:
                    continue
            except (ValueError, TypeError):
                continue

            # Deduplicate by completion text (avoid repeating stock replies)
            norm_completion = completion_text.lower().strip()
            if norm_completion in seen_completions:
                continue
            seen_completions.add(norm_completion)

            # Gather context: up to context_window messages before the prompt
            ctx_start = max(0, i - 1 - context_window)
            ctx_end = i - 1  # exclusive — up to but not including the prompt
            context_msgs = []
            for j in range(ctx_start, ctx_end):
                m = rows[j]
                if m["text"].strip():
                    context_msgs.append({
                        "author_name": m["author_name"],
                        "text": m["text"],
                    })

            pairs.append({
                "context": _format_context_messages(context_msgs),
                "prompt": prompt_text,
                "prompt_author": prev["author_name"],
                "completion": completion_text,
                "thread_name": curr["thread_name"],
                "timestamp": curr["timestamp"],
            })

            if len(pairs) >= max_pairs:
                return pairs

    return pairs
