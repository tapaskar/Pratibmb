"""
Build a compact profile context block for injection into the chat prompt.

Given a query, a target year, and a Profile, this module selects the most
relevant identity information and formats it as a concise text block
(under ~200 tokens) that tells the LLM who it is pretending to be.
"""
from __future__ import annotations
from .schema import Profile


def build_profile_context(profile: Profile, year: int,
                          query: str = "") -> str:
    """Assemble a profile context block for the given year and query."""
    parts = []

    # Identity line
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
            style_bits.append(f"your messages are short (avg {avg} words)")
        if style_bits:
            parts.append("Style: " + "; ".join(style_bits) + ".")

    # Year summary
    ys = profile.get_year_summary(year)
    if ys and ys.summary:
        parts.append(f"Life in {year}: {ys.summary}")

    # Life events this year
    events = profile.get_events_in(year)
    if events:
        ev_strs = [e.event for e in events if e.confidence >= 0.5][:3]
        if ev_strs:
            parts.append("Key events: " + "; ".join(ev_strs) + ".")

    # Relevant relationships
    rels = profile.get_relationships_active_in(year)
    # Sort by message count, take top 5
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
