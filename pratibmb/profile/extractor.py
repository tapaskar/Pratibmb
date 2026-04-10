"""
Profile extraction pipeline.

Uses the chat LLM (Gemma-3-4B) to analyze the user's message corpus and
build a structured profile: relationships, life events, interests, year
summaries, and thread summaries.

This is a one-time batch job (~5-10 minutes on M-series Mac).
"""
from __future__ import annotations
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterator

from ..store import Store
from .schema import (
    Profile, Relationship, LifeEvent, Interest,
    YearSummary, ThreadSummary,
)

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None  # type: ignore


def _ask(llm: "Llama", system: str, user: str, max_tokens: int = 512) -> str:
    """Single LLM call for extraction."""
    llm.reset()
    r = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,  # low temp for factual extraction
        top_p=0.9,
        max_tokens=max_tokens,
    )
    return r["choices"][0]["message"]["content"].strip()


def _parse_json(text: str) -> dict | list | None:
    """Extract JSON from LLM output, handling markdown code blocks."""
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try extracting from ```json ... ``` blocks
    m = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    # Try finding first { or [ to last } or ]
    for start, end in [("{", "}"), ("[", "]")]:
        i = text.find(start)
        j = text.rfind(end)
        if i >= 0 and j > i:
            try:
                return json.loads(text[i:j + 1])
            except json.JSONDecodeError:
                pass
    return None


class ProfileExtractor:
    """Builds a structured Profile from the user's corpus using LLM analysis."""

    SYSTEM = "You are a data analyst. Extract structured information from chat messages. Always respond with valid JSON only, no other text."

    def __init__(self, model_path: Path, n_ctx: int = 4096, n_threads: int = 8):
        if Llama is None:
            raise RuntimeError("llama-cpp-python not installed")
        self.llm = Llama(
            model_path=str(model_path),
            chat_format="gemma",
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_gpu_layers=-1,
            verbose=False,
        )

    def extract(self, store: Store, self_name: str,
                on_progress=None) -> Profile:
        """Run the full extraction pipeline. Returns a Profile."""
        profile = Profile(self_name=self_name)

        def progress(step: str, detail: str = ""):
            if on_progress:
                on_progress(step, detail)
            print(f"[profile] {step} {detail}", flush=True)

        # Step 1: Analyze threads → relationships + thread summaries
        progress("relationships", "analyzing threads...")
        threads = self._get_thread_stats(store, self_name)
        for i, (tid, info) in enumerate(threads.items()):
            progress("relationships", f"thread {i+1}/{len(threads)}: {info['name']}")
            rel, ts = self._analyze_thread(store, tid, info, self_name)
            if rel:
                profile.relationships.append(rel)
            if ts:
                profile.thread_summaries.append(ts)

        # Step 2: Extract life events per year
        progress("life_events", "scanning for life events...")
        years = self._get_years(store)
        for year in years:
            progress("life_events", f"year {year}")
            events = self._extract_year_events(store, year, self_name)
            profile.life_events.extend(events)

        # Step 3: Year summaries
        progress("year_summaries", "building year summaries...")
        for year in years:
            progress("year_summaries", f"year {year}")
            ys = self._build_year_summary(store, year, self_name, profile)
            if ys:
                profile.year_summaries.append(ys)

        # Step 4: Communication style (rule-based, no LLM needed)
        progress("communication_style", "analyzing style...")
        profile.communication_style = self._analyze_style(store)

        progress("done", f"{len(profile.relationships)} relationships, "
                 f"{len(profile.life_events)} events, "
                 f"{len(profile.year_summaries)} year summaries")
        return profile

    def _get_thread_stats(self, store: Store, self_name: str) -> dict:
        """Get per-thread message counts and metadata."""
        rows = store.conn.execute("""
            SELECT thread_id, thread_name,
                   COUNT(*) as total,
                   SUM(CASE WHEN author='self' THEN 1 ELSE 0 END) as self_count,
                   MIN(year) as first_year,
                   MAX(year) as last_year
            FROM messages
            GROUP BY thread_id
            HAVING total >= 5
            ORDER BY self_count DESC
        """).fetchall()
        threads = {}
        for r in rows:
            threads[r["thread_id"]] = {
                "name": r["thread_name"],
                "total": r["total"],
                "self_count": r["self_count"],
                "first_year": r["first_year"],
                "last_year": r["last_year"],
            }
        return threads

    def _analyze_thread(self, store: Store, thread_id: str,
                        info: dict, self_name: str
                        ) -> tuple[Relationship | None, ThreadSummary | None]:
        """Analyze a single thread for relationship and summary."""
        # Get a sample of messages from this thread
        rows = store.conn.execute("""
            SELECT author_name, text, timestamp
            FROM messages
            WHERE thread_id = ? AND text != ''
            ORDER BY timestamp ASC
        """, (thread_id,)).fetchall()

        if len(rows) < 5:
            return None, None

        # Sample evenly: first 5, last 5, 10 from middle
        sample_indices = set()
        n = len(rows)
        for i in range(min(5, n)):
            sample_indices.add(i)
        for i in range(max(0, n - 5), n):
            sample_indices.add(i)
        step = max(1, n // 10)
        for i in range(0, n, step):
            sample_indices.add(i)
            if len(sample_indices) >= 20:
                break

        sample = [rows[i] for i in sorted(sample_indices)]
        msg_block = "\n".join(
            f"[{r['timestamp'][:10]}] {r['author_name']}: {r['text'][:150]}"
            for r in sample
        )

        # Determine other person's name
        other_names = set()
        for r in rows:
            if r["author_name"] != self_name:
                other_names.add(r["author_name"])
        other = ", ".join(other_names) if other_names else info["name"]

        prompt = f"""Analyze this conversation between {self_name} and {other}.

Messages:
{msg_block}

Respond with JSON:
{{
  "relation_type": "close_friend" or "family" or "colleague" or "acquaintance" or "romantic" or "group",
  "topics": ["topic1", "topic2", "topic3"],
  "summary": "one sentence describing this relationship and what they typically talk about"
}}"""

        raw = _ask(self.llm, self.SYSTEM, prompt, max_tokens=200)
        data = _parse_json(raw)

        rel = None
        if data and isinstance(data, dict):
            rel = Relationship(
                person_name=other,
                thread_id=thread_id,
                thread_name=info["name"],
                relation_type=data.get("relation_type", "acquaintance"),
                message_count=info["total"],
                self_message_count=info["self_count"],
                first_year=info["first_year"],
                last_year=info["last_year"],
                topics=data.get("topics", [])[:5],
                summary=data.get("summary", ""),
            )

        ts = ThreadSummary(
            thread_id=thread_id,
            thread_name=info["name"],
            summary=data.get("summary", "") if data else "",
            message_count=info["total"],
            self_message_count=info["self_count"],
            year_start=info["first_year"],
            year_end=info["last_year"],
        )
        return rel, ts

    def _get_years(self, store: Store) -> list[int]:
        rows = store.conn.execute(
            "SELECT DISTINCT year FROM messages WHERE author='self' ORDER BY year"
        ).fetchall()
        return [r["year"] for r in rows]

    def _extract_year_events(self, store: Store, year: int,
                             self_name: str) -> list[LifeEvent]:
        """Extract life events from a specific year's messages."""
        rows = store.conn.execute("""
            SELECT text, timestamp, thread_name
            FROM messages
            WHERE author='self' AND year = ? AND text != ''
            ORDER BY timestamp ASC
        """, (year,)).fetchall()

        if len(rows) < 3:
            return []

        # Sample messages from this year
        step = max(1, len(rows) // 30)
        sample = rows[::step][:30]

        msg_block = "\n".join(
            f"[{r['timestamp'][:10]} in {r['thread_name']}] {r['text'][:150]}"
            for r in sample
        )

        prompt = f"""These are messages sent by {self_name} in {year}.
Identify any significant life events mentioned or implied (job changes, moves, relationships, achievements, losses, travel, education).

Messages:
{msg_block}

Respond with JSON array (empty array if no events found):
[
  {{"event": "description", "category": "career/relationship/move/education/personal/travel", "month": null or 1-12, "confidence": 0.0-1.0, "evidence": "the message that suggests this"}}
]"""

        raw = _ask(self.llm, self.SYSTEM, prompt, max_tokens=400)
        data = _parse_json(raw)

        events = []
        if data and isinstance(data, list):
            for item in data[:5]:  # max 5 events per year
                if not isinstance(item, dict):
                    continue
                events.append(LifeEvent(
                    year=year,
                    month=item.get("month"),
                    event=item.get("event", ""),
                    category=item.get("category", "personal"),
                    confidence=float(item.get("confidence", 0.5)),
                    evidence=[item.get("evidence", "")][:3],
                ))
        return events

    def _build_year_summary(self, store: Store, year: int,
                            self_name: str, profile: Profile) -> YearSummary | None:
        """Build a year summary combining stats + LLM analysis."""
        count = store.count(year_max=year, author="self")
        # Get this year's count specifically
        year_count = store.conn.execute(
            "SELECT COUNT(*) FROM messages WHERE author='self' AND year=?",
            (year,)
        ).fetchone()[0]

        if year_count < 3:
            return None

        # Get top people this year
        top_people = store.conn.execute("""
            SELECT thread_name, COUNT(*) as cnt
            FROM messages
            WHERE year = ? AND author = 'other'
            GROUP BY thread_name
            ORDER BY cnt DESC
            LIMIT 5
        """, (year,)).fetchall()
        people = [r["thread_name"] for r in top_people]

        # Get sample messages for summary
        rows = store.conn.execute("""
            SELECT text, timestamp, thread_name
            FROM messages
            WHERE author='self' AND year = ? AND text != ''
            ORDER BY timestamp ASC
        """, (year,)).fetchall()

        step = max(1, len(rows) // 20)
        sample = rows[::step][:20]

        msg_block = "\n".join(
            f"[{r['timestamp'][:7]}] {r['text'][:120]}"
            for r in sample
        )

        # Include events we already found
        events_this_year = [e for e in profile.life_events if e.year == year]
        events_text = ""
        if events_this_year:
            events_text = "\nKnown events this year: " + "; ".join(
                e.event for e in events_this_year
            )

        prompt = f"""Write a 2-3 sentence summary of {self_name}'s life in {year} based on these messages.
Focus on: what was going on, how they were feeling, key relationships, what mattered to them.
{events_text}

Messages:
{msg_block}

Respond with JSON:
{{"summary": "2-3 sentence summary", "top_topics": ["topic1", "topic2", "topic3"]}}"""

        raw = _ask(self.llm, self.SYSTEM, prompt, max_tokens=250)
        data = _parse_json(raw)

        summary_text = ""
        topics = []
        if data and isinstance(data, dict):
            summary_text = data.get("summary", "")
            topics = data.get("top_topics", [])[:5]

        return YearSummary(
            year=year,
            summary=summary_text,
            message_count=year_count,
            top_people=people,
            top_topics=topics,
        )

    def _analyze_style(self, store: Store) -> dict:
        """Rule-based communication style analysis (no LLM needed)."""
        rows = store.conn.execute("""
            SELECT text FROM messages WHERE author='self' AND text != ''
        """).fetchall()

        if not rows:
            return {}

        total = len(rows)
        texts = [r["text"] for r in rows]

        # Lowercase ratio
        lowercase_count = sum(1 for t in texts if t == t.lower())

        # Average length
        avg_words = sum(len(t.split()) for t in texts) / total

        # Short message ratio
        short = sum(1 for t in texts if len(t.split()) <= 5)

        # Language detection (Hinglish markers)
        hinglish_words = {"hai", "nahi", "kya", "mein", "yaar", "bhai",
                          "acha", "haan", "theek", "kaise", "waha", "abhi",
                          "abt", "aur", "toh", "bol", "chal", "dekh"}
        all_words = " ".join(texts).lower().split()
        hinglish_count = sum(1 for w in all_words if w in hinglish_words)
        hinglish_ratio = hinglish_count / max(len(all_words), 1)

        # Emoji usage
        import re
        emoji_pattern = re.compile(
            "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF"
            "\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF"
            "\U00002702-\U000027B0\U0001F900-\U0001F9FF]+",
            flags=re.UNICODE,
        )
        emoji_msgs = sum(1 for t in texts if emoji_pattern.search(t))

        return {
            "lowercase_ratio": round(lowercase_count / total, 2),
            "avg_words_per_message": round(avg_words, 1),
            "short_message_ratio": round(short / total, 2),
            "hinglish_ratio": round(hinglish_ratio, 3),
            "uses_hinglish": hinglish_ratio > 0.01,
            "emoji_usage_ratio": round(emoji_msgs / total, 2),
            "total_messages": total,
        }
