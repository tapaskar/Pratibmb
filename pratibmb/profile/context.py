"""
Build a profile context block for injection into the chat prompt.

Given a query, a target year, and a Profile, this module selects the most
relevant identity information. For identity questions, injects a rich
self-portrait. For normal chat, keeps it compact (~200 tokens).
"""
from __future__ import annotations
import re
from .schema import Profile


_RICH_CONTEXT_PATTERNS = re.compile(
    r"("
    # Identity / self-description
    r"who am i|who are you|tell me about (yourself|you|me)|"
    r"do you know me|know who i am|about yourself|introduce yourself|"
    r"what do you do|where (are you|do you live)|what'?s your (name|life)|"
    r"describe yourself|your life|"
    # Career / work
    r"(where|what) (do|did) you work|your (job|career|company)|"
    r"kya karte ho|kaha job|kaunsi company|"
    # Relationships / people
    r"(your|tumhari|teri) (girlfriend|wife|gf|family|biwi)|"
    r"who.{0,10}(close|best friend|important)|"
    r"relationship|married|single|"
    # Life events / memories
    r"remember when|yaad hai|college (days|time|life)|"
    r"school (days|time)|bachpan|childhood|"
    r"biggest (moment|change|achievement|regret)|"
    r"how (has|have) you changed|life journey|"
    # Location / living
    r"where (have you|did you) live|kahan rehte|"
    r"which city|moved to|shifted to|"
    # Interests / personality
    r"what (are|were) your (interests|hobbies|passion)|"
    r"kya pasand|what do you like|favorite|favourite|"
    r"what kind of person|personality|"
    # Nostalgia / reflection
    r"how was (your |)(life|year|time) in|"
    r"what (happened|were you doing) in|"
    r"(back in|during) (20\d\d|college|school)|"
    r"look(ing)? back|those days|purane din|"
    # Emotional / deep
    r"how (are|do) you feel|what matters|"
    r"what (have you|did you) learn|regret|proud of|"
    r"happiest|saddest|toughest|best (time|year|phase)"
    r")",
    re.IGNORECASE,
)


def _is_identity_query(query: str) -> bool:
    """Check if the query needs rich profile context."""
    return bool(_RICH_CONTEXT_PATTERNS.search(query))


def build_profile_context(profile: Profile, year: int,
                          query: str = "") -> str:
    """Assemble a profile context block for the given year and query.

    For identity questions, returns a rich profile (~500 tokens).
    For normal chat, returns a compact summary (~200 tokens).
    """
    if query and _is_identity_query(query):
        return _build_rich_context(profile, year, query)
    return _build_compact_context(profile, year, query)


def _build_rich_context(profile: Profile, year: int, query: str) -> str:
    """Rich profile for identity questions — who am I, tell me about yourself."""
    parts = []

    parts.append(f"You are {profile.self_name}. The year is {year}.")

    # Communication style
    style = profile.communication_style
    if style:
        style_bits = []
        if style.get("uses_hinglish"):
            style_bits.append("you naturally mix Hindi, English, and sometimes Odia (Hinglish)")
        avg = style.get("avg_words_per_message", 0)
        if avg:
            style_bits.append(f"you text casually with short messages")
        if style_bits:
            parts.append("Communication: " + "; ".join(style_bits) + ".")

    # Current year summary — this is the core identity
    ys = profile.get_year_summary(year)
    if ys and ys.summary:
        parts.append(f"\nYour life in {year}: {ys.summary}")

    # Also include previous year for context
    prev_ys = profile.get_year_summary(year - 1)
    if prev_ys and prev_ys.summary:
        parts.append(f"Previously ({year-1}): {prev_ys.summary}")

    # Life events around this year
    for y in range(year - 1, year + 1):
        events = profile.get_events_in(y)
        if events:
            ev_strs = [e.event for e in events if e.event][:4]
            if ev_strs:
                parts.append(f"Events ({y}): " + "; ".join(ev_strs))

    # Top relationships with detail
    rels = profile.get_relationships_active_in(year)
    rels = sorted(rels, key=lambda r: r.message_count, reverse=True)[:8]
    if rels:
        parts.append("\nPeople in your life:")
        for r in rels:
            line = f"  - {r.person_name}"
            if r.relation_type:
                line += f" ({r.relation_type})"
            if r.summary:
                line += f": {r.summary[:120]}"
            elif r.topics:
                line += f": talk about {', '.join(r.topics[:3])}"
            parts.append(line)

    # Interests
    interests = profile.get_interests_in(year)
    if interests:
        int_strs = [i.topic for i in interests][:6]
        parts.append(f"\nInterests: {', '.join(int_strs)}")

    # Earlier year summaries for life arc
    arc_parts = []
    for y in sorted(set(ys.year for ys in profile.year_summaries if ys.year < year)):
        ys_item = profile.get_year_summary(y)
        if ys_item and ys_item.summary:
            # Just first sentence for earlier years
            first_sentence = ys_item.summary.split('.')[0] + '.'
            arc_parts.append(f"  {y}: {first_sentence}")
    if arc_parts:
        parts.append("\nYour journey:")
        parts.extend(arc_parts[-5:])  # Last 5 years before current

    parts.append(
        "\nYou know your own life deeply — use ALL of the above information. "
        "Share details naturally, mention real people and events from your life. "
        "You are NOT an AI, NOT a language model. You are a real person with this history. "
        "Never say you're an AI or a chatbot. You are " + profile.self_name + "."
    )

    return "\n".join(parts)


def _build_compact_context(profile: Profile, year: int, query: str) -> str:
    """Compact profile for normal chat — ~200 tokens."""
    parts = []

    parts.append(f"You are {profile.self_name}, year {year}.")

    # Communication style
    style = profile.communication_style
    if style:
        style_bits = []
        if style.get("uses_hinglish"):
            style_bits.append("you mix Hindi and English (Hinglish)")
        lr = style.get("lowercase_ratio", 0)
        if lr > 0.8:
            style_bits.append("you write almost entirely in lowercase")
        avg = style.get("avg_words_per_message", 0)
        if avg < 8:
            style_bits.append(f"your messages are short (avg {avg:.0f} words)")
        if style_bits:
            parts.append("Style: " + "; ".join(style_bits) + ".")

    # Year summary
    ys = profile.get_year_summary(year)
    if ys and ys.summary:
        parts.append(f"Life in {year}: {ys.summary}")

    # Life events this year
    events = profile.get_events_in(year)
    if events:
        ev_strs = [e.event for e in events if e.event and e.confidence >= 0.5][:3]
        if ev_strs:
            parts.append("Key events: " + "; ".join(ev_strs) + ".")

    # Relevant relationships
    rels = profile.get_relationships_active_in(year)
    rels = sorted(rels, key=lambda r: r.message_count, reverse=True)[:5]
    if rels:
        rel_strs = []
        for r in rels:
            topics = ", ".join(r.topics[:2]) if r.topics else ""
            desc = f"{r.person_name} ({r.relation_type}"
            if topics:
                desc += f", talk about {topics}"
            desc += ")"
            rel_strs.append(desc)
        parts.append("People in your life: " + "; ".join(rel_strs) + ".")

    # If query mentions a specific person, add that relationship detail
    if query:
        query_lower = query.lower()
        for r in profile.relationships:
            if r.person_name.lower() in query_lower and r.summary:
                parts.append(f"About {r.person_name}: {r.summary}")
                break

    return "\n".join(parts)


def build_thread_context(messages: list[dict], max_messages: int = 12) -> str:
    """Format retrieved messages with their thread context as conversation snippets.

    Input: list of dicts with keys: text, timestamp, thread_name, author_name,
           plus optional 'context_before' and 'context_after' lists.
    """
    if not messages:
        return "<past_conversations>(none)</past_conversations>"

    # Group by thread
    threads: dict[str, list[dict]] = {}
    for m in messages[:max_messages]:
        tn = m.get("thread_name", "unknown")
        threads.setdefault(tn, []).append(m)

    lines = []
    for thread_name, msgs in threads.items():
        # Sort by timestamp
        msgs.sort(key=lambda x: x.get("timestamp", ""))
        lines.append(f"[Thread: {thread_name}]")
        for m in msgs:
            # Include context before/after if available
            for ctx in m.get("context_before", []):
                lines.append(f"  {ctx['author_name']}: {ctx['text'][:120]}")
            # The actual retrieved message
            name = m.get("author_name", "you")
            lines.append(f"  {name}: {m['text'][:150]}")
            for ctx in m.get("context_after", []):
                lines.append(f"  {ctx['author_name']}: {ctx['text'][:120]}")
        lines.append("")

    inner = "\n".join(lines).strip()
    return f"<past_conversations>\n{inner}\n</past_conversations>"
