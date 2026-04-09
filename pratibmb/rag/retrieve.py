"""
Year-filtered cosine-similarity retrieval over the SQLite store.

Only `author = 'self'` messages are considered context — we want past-you's
voice, not what other people said to you.
"""
from __future__ import annotations
import numpy as np
from ..store import Store


class Retriever:
    def __init__(self, store: Store, embedder):
        self.store = store
        self.embedder = embedder

    def retrieve(self, query: str, year_max: int, top_k: int = 8) -> list[dict]:
        ids, corpus = self.store.load_embeddings(year_max=year_max, author="self")
        if corpus.shape[0] == 0:
            return []
        q_vec = self.embedder.embed([query])[0]
        q = q_vec.astype(np.float32)
        qn = np.linalg.norm(q)
        if qn == 0:
            return []
        q = q / qn
        # Filter out zero-norm vectors to avoid NaN in cosine similarity
        norms = np.linalg.norm(corpus, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)  # avoid div-by-zero
        corpus = corpus / norms
        sims = corpus @ q
        # Light time-decay: small boost to more recent messages within window.
        # (kept simple; ranking is dominated by cosine)
        order = np.argsort(-sims)[:top_k]
        chosen_ids = [ids[i] for i in order]
        rows = self.store.get_messages(chosen_ids)
        by_id = {r["id"]: r for r in rows}
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
                "source": row["source"],
                "score": float(sims[i]),
                "rank": rank,
            })
        return out


def format_context(messages: list[dict]) -> str:
    if not messages:
        return "<past_messages_you_sent>(none)</past_messages_you_sent>"
    lines = []
    for m in messages:
        ts = m["timestamp"][:10]
        lines.append(f"[{ts} · {m['thread_name']}] {m['text']}")
    inner = "\n".join(lines)
    return f"<past_messages_you_sent>\n{inner}\n</past_messages_you_sent>"
