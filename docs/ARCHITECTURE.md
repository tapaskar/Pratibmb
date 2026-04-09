# Pratibmb Architecture

## Non-negotiables

1. **Runs offline.** No network call after first-run model download.
2. **Data stays local.** The user's messages never leave the machine.
3. **Auditable.** Source is public. No telemetry. Ever.

## Data flow

```
 exports (WhatsApp .txt, Facebook DYI, Instagram DYI, ...)
            │
            ▼
   ┌────────────────┐
   │   Importers    │  pluggable; each produces normalized Message objects
   └────────────────┘
            │
            ▼
   ┌────────────────┐
   │  SQLite store  │  messages + embeddings (float32 BLOBs)
   └────────────────┘
            │
            ▼
   ┌────────────────┐
   │ Voice extract  │  stylistic fingerprint of YOUR messages
   └────────────────┘
            │
            ▼
   ┌────────────────┐     retrieve top-k (year-filtered)
   │      RAG       │◀──── cosine similarity over self-message embeddings
   └────────────────┘
            │
            ▼
   ┌────────────────┐
   │  llama.cpp     │  Gemma-3-4B-Instruct Q4_K_M
   │   (chat LLM)   │  system prompt = persona + voice directive
   └────────────────┘
            │
            ▼
        past-you's reply
```

## Components

### `pratibmb.schema`
A single `Message` dataclass. Every importer emits these. Source-agnostic by design.

### `pratibmb.importers`
Pluggable importer layer. A new source = one new file implementing `Importer`. The protocol is tiny: `name`, `detect(path)`, `load(path, self_name)`. Importers stream — they never load an entire export into memory.

v1 importers:
- `whatsapp.py` — iOS/Android "Export Chat" `.txt`
- `facebook.py` — Facebook DYI JSON (Messenger threads + posts)
- `instagram.py` — Instagram DYI JSON (DMs + posts)

Planned: Gmail mbox, iMessage `chat.db`, Telegram export, Twitter archive, Discord export.

### `pratibmb.store.sqlite`
Flat SQLite schema: `messages`, `embeddings`, `meta`. Embeddings are float32 BLOBs. We don't rely on `sqlite-vec` yet — brute-force cosine over 100k vectors is sub-100ms on M-series Macs. When the corpus gets larger we'll swap in sqlite-vec or a HNSW index.

### `pratibmb.rag`
`Embedder` wraps llama.cpp in embedding mode (GGUF embedding model — keeps the runtime stack 100% llama.cpp, no Python ML deps in the shipped binary).
`Retriever` does year-filtered cosine search over `author = 'self'` only — we want past-you's voice, not what other people said.

### `pratibmb.voice`
Deterministic one-pass fingerprint of the user's own writing: lowercase ratio, typical message length, favorite phrases, emoji use. Rendered into a one-line style directive injected into the system prompt.

### `pratibmb.llm`
`Chatter` wraps llama.cpp for chat generation. System prompt locks the model into "you are the user in year Y" and forbids assistant-speak. v1 ships a standalone llama.cpp server binary; this Python path is for dev and the CLI.

### `pratibmb.cli`
Click-based CLI: `init`, `import`, `embed`, `voice`, `chat`, `stats`. The desktop app (Tauri) will call into the same Python library during development, and into a llama.cpp server at ship time.

## Model selection

Selected after:
1. A **blind manual eval** of 6 candidates (Llama-3.2-3B, Llama-3.1-8B, Mistral-7B, Qwen2.5-7B, Gemma-3-4B, Gemma-2-9B) on a 10-prompt test set.
2. An **automated head-to-head** of the top contender vs Gemma-4-E4B, judged by Qwen2.5-7B with A/B position randomization.

Winner: **Gemma-3-4B-Instruct Q4_K_M** (2.32 GB, fastest of the top tier, wins on voice / grounding / emotion / style against every other candidate including newer models).

Full results in `docs/MODEL_EVAL.md`.

## What's next

- [ ] `pratibmb-desktop` — Tauri shell with drag-and-drop onboarding and year slider
- [ ] Embed cache for first-run experience
- [ ] Safety rails: session time limits, gentle reframes on grief spirals
- [ ] Gmail / iMessage / Telegram importers
- [ ] "Memory book" PDF export
- [ ] Cross-platform signed builds
