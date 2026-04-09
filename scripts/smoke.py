"""
End-to-end smoke test for Pratibmb.

Loads the synthetic WhatsApp corpus produced during model selection
(/Volumes/wininstall/llm-eval/corpus.json), imports it into a temporary
Pratibmb store, embeds it with the bundled nomic GGUF embedding model,
fingerprints the voice, retrieves context for a test prompt, and runs
one chat turn through Gemma-3-4B.

Run:
    python scripts/smoke.py
"""
from __future__ import annotations
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pratibmb.schema import Message
from pratibmb.store import Store
from pratibmb.rag import Embedder, Retriever, format_context
from pratibmb.voice import fingerprint, render_voice_directive
from pratibmb.llm import Chatter

CORPUS = Path("/Volumes/wininstall/llm-eval/corpus.json")
EMBED_MODEL = Path("/Volumes/wininstall/llm-eval/models/nomic-embed-text-v1.5-q4_k_m.gguf")
CHAT_MODEL = Path("/Volumes/wininstall/llm-eval/models/gemma-3-4b-it-q4_k_m.gguf")

SELF_NAME = "you"


def as_messages(raw: list[dict]) -> list[Message]:
    out: list[Message] = []
    for r in raw:
        ts = datetime.fromisoformat(r["timestamp"]).replace(tzinfo=timezone.utc)
        # corpus format: {timestamp, chat, text, year}
        # Everything in the synthetic corpus was authored by 'you'.
        out.append(Message(
            source="whatsapp",
            timestamp=ts,
            author="self",
            author_name=SELF_NAME,
            text=r["text"],
            thread_id=f"whatsapp::{r['chat']}",
            thread_name=r["chat"],
        ))
    return out


def main() -> None:
    assert CORPUS.exists(), f"missing synthetic corpus at {CORPUS}"
    assert EMBED_MODEL.exists(), f"missing embed model at {EMBED_MODEL}"
    assert CHAT_MODEL.exists(), f"missing chat model at {CHAT_MODEL}"

    raw = json.loads(CORPUS.read_text())
    print(f"[smoke] loaded {len(raw)} raw messages")

    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "smoke.db"
        store = Store(db)

        n = store.add_messages(as_messages(raw))
        print(f"[smoke] imported {n} messages")
        assert store.count() == n

        print("[smoke] loading embedder...")
        embedder = Embedder(EMBED_MODEL)
        total = 0
        for chunk in store.iter_missing_embeddings(batch=128):
            texts = [row["text"] for row in chunk]
            vecs = embedder.embed(texts)
            store.put_embeddings(list(zip([row["id"] for row in chunk], vecs)))
            total += len(chunk)
        print(f"[smoke] embedded {total} messages")

        fp = fingerprint(store)
        directive = render_voice_directive(fp)
        print(f"[smoke] voice: {directive or '(empty)'}")

        retriever = Retriever(store, embedder)
        prompt = "hey it's future-you. how are you holding up with the new job?"
        hits = retriever.retrieve(prompt, year_max=2023, top_k=8)
        print(f"[smoke] top hit: {hits[0]['text'][:80]!r}  (score={hits[0]['score']:.3f})")
        ctx = format_context(hits)

        print("[smoke] loading chat model...")
        chatter = Chatter(CHAT_MODEL, chat_format="gemma")
        reply = chatter.reply(
            year=2023,
            voice_directive=directive,
            context_block=ctx,
            user_prompt=prompt,
            max_tokens=200,
        )
        print("\n=== past-you says ===")
        print(reply)
        print("\n[smoke] ok")


if __name__ == "__main__":
    main()
