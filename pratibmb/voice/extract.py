"""
One-time voice fingerprinting over the user's own past messages.

Produces a small JSON dict with stylistic features that get injected into
the LLM system prompt. Cheap, deterministic, no model required.
"""
from __future__ import annotations
import json
import re
from collections import Counter
from pathlib import Path
from ..store import Store

_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "]+",
    flags=re.UNICODE,
)
_WORD_RE = re.compile(r"[a-zA-Z']+")
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "of", "to", "in",
    "is", "it", "this", "that", "for", "on", "with", "as", "at", "by",
    "be", "are", "was", "were", "i", "you", "we", "they", "he", "she",
    "me", "my", "your", "our", "their", "his", "her", "so", "not", "no",
    "do", "does", "did", "have", "has", "had", "can", "could", "would",
    "should", "will", "just", "about", "from", "up", "out", "into",
}


def fingerprint(store: Store, year_max: int | None = None,
                max_messages: int = 5000) -> dict:
    texts: list[str] = []
    for i, row in enumerate(store.iter_self_messages(year_max=year_max)):
        if i >= max_messages:
            break
        if row["text"]:
            texts.append(row["text"])

    total = len(texts)
    if total == 0:
        return {"samples": 0}

    chars = 0
    lower_chars = 0
    emojis: Counter[str] = Counter()
    phrases: Counter[str] = Counter()
    lengths: list[int] = []
    typos = 0

    for t in texts:
        chars += len(t)
        lower_chars += sum(1 for c in t if c.islower())
        for e in _EMOJI_RE.findall(t):
            for ch in e:
                emojis[ch] += 1
        words = _WORD_RE.findall(t.lower())
        lengths.append(len(words))
        for w in words:
            if w in _STOPWORDS or len(w) < 3:
                continue
            phrases[w] += 1
        # Cheap typo-ish signal: repeated letters (e.g. "sooo", "helloo")
        if re.search(r"(.)\1{2,}", t):
            typos += 1

    lowercase_ratio = lower_chars / max(1, sum(1 for c in "".join(texts) if c.isalpha()))
    avg_len = sum(lengths) / total
    short_pct = sum(1 for l in lengths if l <= 6) / total
    top_emojis = [e for e, _ in emojis.most_common(10)]
    top_phrases = [p for p, _ in phrases.most_common(20)]

    return {
        "samples": total,
        "avg_words": round(avg_len, 1),
        "short_message_pct": round(short_pct, 2),
        "lowercase_ratio": round(lowercase_ratio, 2),
        "typo_ratio": round(typos / total, 2),
        "top_emojis": top_emojis,
        "top_phrases": top_phrases,
    }


def render_voice_directive(fp: dict) -> str:
    """Turn a fingerprint into a compact voice instruction for the system prompt."""
    if not fp or fp.get("samples", 0) == 0:
        return ""
    bits = []
    if fp.get("lowercase_ratio", 0) > 0.85:
        bits.append("write almost entirely in lowercase")
    if fp.get("short_message_pct", 0) > 0.6:
        bits.append("keep messages short — usually under 15 words")
    if fp.get("typo_ratio", 0) > 0.15:
        bits.append("occasional typos and repeated letters like 'sooo' are fine")
    if fp.get("top_emojis"):
        bits.append(f"sparingly use emojis like {' '.join(fp['top_emojis'][:3])}")
    if fp.get("top_phrases"):
        bits.append("common words you use: " + ", ".join(fp["top_phrases"][:10]))
    return "style notes: " + "; ".join(bits) + "."


def save(fp: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fp, indent=2))
