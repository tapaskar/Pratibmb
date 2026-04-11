"""
Year-filtered retrieval with thread-context expansion.

Retrieves semantically similar self-authored messages, then expands each
with surrounding thread context so the LLM sees full conversation flow,
not isolated fragments.
"""
from __future__ import annotations
import numpy as np
from ..store import Store


class Retriever:
    def __init__(self, store: Store, embedder):
        self.store = store
        self.embedder = embedder

    def retrieve(self, query: str, year_max: int, top_k: int = 8,
                 thread_window: int = 3) -> list[dict]:
        """Retrieve top-k messages with thread context expansion."""
        ids, corpus = self.store.load_embeddings(year_max=year_max, author="self")
        if corpus.shape[0] == 0:
            return []
        q_vec = self.embedder.embed([query])[0]
        q = q_vec.astype(np.float32)
        qn = np.linalg.norm(q)
        if qn == 0:
            return []
        q = q / qn

        # Clean corpus: replace NaN/inf with zero, then normalize.
        # Some stored embeddings may contain NaN or extreme values from
        # corrupted batches. We clamp and normalize to ensure valid cosine sim.
        corpus = np.nan_to_num(corpus, nan=0.0, posinf=0.0, neginf=0.0)
        norms = np.linalg.norm(corpus, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        corpus = corpus / norms
        with np.errstate(all="ignore"):
            sims = corpus @ q
        # Clamp any remaining NaN/inf scores to 0
        sims = np.nan_to_num(sims, nan=0.0, posinf=0.0, neginf=0.0)

        order = np.argsort(-sims)[:top_k]
        chosen_ids = [ids[i] for i in order]

        # Get messages with thread context
        enriched = self.store.get_messages_enriched(
            chosen_ids, thread_window=thread_window
        )
        by_id = {r["id"]: r for r in enriched}

        out = []
        for rank, i in enumerate(order):
            row = by_id.get(ids[i])
            if row is None:
                continue
            out.append({
                "id": row["id"],
                "text": row["text"],
                "timestamp": row["timestamp"],
                "year": row["year"],
                "thread_name": row["thread_name"],
                "author_name": row.get("author_name", ""),
                "source": row["source"],
                "score": float(sims[i]),
                "rank": rank,
                "context_before": row.get("context_before", []),
                "context_after": row.get("context_after", []),
            })
        return out


def format_context(messages: list[dict]) -> str:
    """Format retrieved messages as conversation snippets with thread context."""
    if not messages:
        return "<past_conversations>(none)</past_conversations>"

    # Group by thread to show coherent conversation flow
    threads: dict[str, list[dict]] = {}
    for m in messages:
        tn = m.get("thread_name", "unknown")
        threads.setdefault(tn, []).append(m)

    lines = []
    for thread_name, msgs in threads.items():
        msgs.sort(key=lambda x: x.get("timestamp", ""))
        lines.append(f"[Thread: {thread_name}]")

        seen_texts = set()  # avoid duplicate context lines
        for m in msgs:
            # Context before (other person's messages leading up to yours)
            for ctx in m.get("context_before", []):
                txt = ctx["text"][:120]
                key = (ctx.get("author_name", ""), txt)
                if key not in seen_texts:
                    seen_texts.add(key)
                    lines.append(f"  {ctx['author_name']}: {txt}")

            # The actual retrieved self-message
            lines.append(f"  {m.get('author_name', 'you')}: {m['text'][:150]}")
            seen_texts.add((m.get("author_name", ""), m["text"][:150]))

            # Context after
            for ctx in m.get("context_after", []):
                txt = ctx["text"][:120]
                key = (ctx.get("author_name", ""), txt)
                if key not in seen_texts:
                    seen_texts.add(key)
                    lines.append(f"  {ctx['author_name']}: {txt}")
        lines.append("")

    inner = "\n".join(lines).strip()
    return f"<past_conversations>\n{inner}\n</past_conversations>"
