# Pratibmb Architecture

## Non-negotiables

1. **Runs offline.** No network call after first-run model download.
2. **Data stays local.** The user's messages never leave the machine.
3. **Auditable.** Source is public. No telemetry. Ever.

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        USER'S MACHINE                                   │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Tauri Desktop App (.dmg / .exe / .deb / .AppImage)             │   │
│  │                                                                  │   │
│  │  ┌──────────────────┐     ┌──────────────────────────────────┐  │   │
│  │  │  WebView (UI)    │     │  Rust Backend (main.rs)          │  │   │
│  │  │  index.html      │◄───►│  - Spawns Python sidecar         │  │   │
│  │  │  app.js          │ IPC │  - Proxies commands via reqwest  │  │   │
│  │  │  style.css       │     │  - Process lifecycle management  │  │   │
│  │  └──────────────────┘     └──────────┬───────────────────────┘  │   │
│  │                                      │ HTTP (127.0.0.1:11435)   │   │
│  └──────────────────────────────────────┼──────────────────────────┘   │
│                                         │                               │
│  ┌──────────────────────────────────────▼──────────────────────────┐   │
│  │  Python Server (pratibmb.server)                                │   │
│  │  stdlib HTTPServer — no Flask/FastAPI                            │   │
│  │                                                                  │   │
│  │  ┌─────────────┐ ┌──────────────┐ ┌───────────────────────────┐│   │
│  │  │  Importers   │ │  RAG Engine  │ │  LLM Chat Engine         ││   │
│  │  │  8 platforms │ │  embed+cosine│ │  Gemma-3-4B via llama.cpp││   │
│  │  └─────────────┘ └──────┬───────┘ └──────────┬────────────────┘│   │
│  │                          │                     │                 │   │
│  │  ┌───────────────────────▼─────────────────────▼──────────────┐ │   │
│  │  │  llama-cpp-python (Metal / CUDA / CPU)                     │ │   │
│  │  │  - Chat: gemma-3-4b-it Q4_K_M (2.3 GB GGUF)              │ │   │
│  │  │  - Embed: nomic-embed-text-v1.5 Q4_K_M (84 MB GGUF)      │ │   │
│  │  │  - LoRA adapter: adapter.gguf (~10 MB, optional)           │ │   │
│  │  └────────────────────────────────────────────────────────────┘ │   │
│  │                          │                                      │   │
│  │  ┌───────────────────────▼────────────────────────────────────┐ │   │
│  │  │  SQLite Store                                              │ │   │
│  │  │  - messages (corpus from 8 platform importers)             │ │   │
│  │  │  - embeddings (float32 BLOBs, cosine-searchable)           │ │   │
│  │  │  - profile (relationships, life events, year summaries)    │ │   │
│  │  │  - meta (config, voice fingerprint)                        │ │   │
│  │  └────────────────────────────────────────────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                         │
│  ~/.pratibmb/                                                           │
│  ├── models/                                                            │
│  │   ├── gemma-3-4b-it-q4_k_m.gguf              (2.3 GB, auto-download)│
│  │   ├── nomic-embed-text-v1.5-q4_k_m.gguf      (84 MB, auto-download) │
│  │   ├── pratibmb-*-finetuned-q4_k_m.gguf        (2.7 GB, after train) │
│  │   └── adapter.gguf                             (~10 MB, after train) │
│  ├── data/                                                              │
│  │   └── pratibmb.db                              (SQLite corpus)       │
│  └── finetune/                                                          │
│      ├── data/train.jsonl                         (training pairs)      │
│      └── adapter/                                 (LoRA weights)        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘

         ▲ ONE-TIME ONLY (first launch)
         │
    ┌────┴─────────────────────────────────────────────┐
    │  HuggingFace Hub (public, no auth required)      │
    │                                                   │
    │  bartowski/google_gemma-3-4b-it-GGUF             │
    │    └── google_gemma-3-4b-it-Q4_K_M.gguf (2.49GB)│
    │                                                   │
    │  nomic-ai/nomic-embed-text-v1.5-GGUF             │
    │    └── nomic-embed-text-v1.5.Q4_K_M.gguf (84MB) │
    └──────────────────────────────────────────────────┘
```

## Chat Turn Pipeline

```
  User types a question for year Y
          │
          ▼
  ┌───────────────────┐
  │ Embed query       │  nomic-embed-text-v1.5 (84 MB)
  └─────────┬─────────┘
            │ 384-dim vector
            ▼
  ┌───────────────────┐
  │ Cosine retrieval  │  top-8 messages from year Y, self-authored only
  │ + thread context  │  each match expands to ±3 surrounding messages
  └─────────┬─────────┘
            │
            ▼
  ┌───────────────────┐
  │ Profile context   │  year-specific identity block (~200 tokens)
  │ builder           │  relationships, life events, style directive
  └─────────┬─────────┘
            │
            ▼
  ┌───────────────────┐
  │ System prompt     │  persona + voice + profile + retrieved memories
  │ assembly          │  "You are [name], year [Y]. Style: [voice]."
  └─────────┬─────────┘
            │
            ▼
  ┌───────────────────┐
  │ Gemma-3-4B        │  llama-cpp-python + optional LoRA adapter
  │ generate reply    │  temp=0.8, top_p=0.85, repeat_penalty=1.2
  └─────────┬─────────┘
            │
            ▼
  ┌───────────────────┐
  │ Post-processor    │  anti-copy guard, 4-sentence truncation,
  │                   │  continuation loop if response is incomplete
  └─────────┬─────────┘
            │
            ▼
      Past-you's reply
```

## Fine-Tuning Pipeline

```
  Corpus (SQLite)
      │
      ▼
  ┌─────────────────┐
  │ Extract pairs    │  Find (other→self) message transitions
  │                  │  Include 2-3 prior messages as context
  │                  │  ~2,500 pairs from typical corpus
  └────────┬────────┘
           │ train.jsonl
           ▼
  ┌─────────────────┐
  │ Format for Gemma │  Gemma chat template with <start_of_turn>
  └────────┬────────┘
           │
           ▼
  ┌─────────────────────────────────────────────────┐
  │ Train LoRA adapter                              │
  │                                                  │
  │ macOS Apple Silicon: MLX-LM (Metal, ~20 min)    │  ◄── included
  │ Windows/Linux NVIDIA: PyTorch+QLoRA (~30 min)   │  ◄── optional add-on
  │ Linux CPU-only: PyTorch (~2 hours)              │
  │                                                  │
  │ LoRA rank=16, alpha=32, targets=q/k/v/o_proj    │
  └────────┬────────────────────────────────────────┘
           │ adapter_model.safetensors
           ▼
  ┌─────────────────┐
  │ Convert to GGUF  │  llama.cpp convert_lora_to_gguf.py
  └────────┬────────┘
           │ adapter.gguf (~10 MB)
           ▼
  ~/.pratibmb/models/adapter.gguf
  (auto-detected at next chat)
```

## Distribution Architecture

```
  ┌──────────────────────────────────────────────────────────────────┐
  │  Main Repo: tapaskar/Pratibmb (source of truth)                 │
  │                                                                  │
  │  .github/workflows/                                              │
  │  ├── build-desktop.yml     ─── tag push ──► 4 platform builds   │
  │  ├── deploy-site.yml       ─── push main ──► pratibmb.com       │
  │  └── publish-packages.yml  ─── release ──► update dist repos    │
  └──────────────┬───────────────────────────────────────────────────┘
                 │ on release published
                 ▼
  ┌──────────────────────────────┐  ┌─────────────────────────────┐
  │ tapaskar/homebrew-pratibmb   │  │ tapaskar/pratibmb-winget    │
  │ brew tap + install --cask    │  │ winget install tapaskar.P.. │
  │ auto-updated SHA256 + ver    │  │ auto-updated SHA256 + ver   │
  └──────────────────────────────┘  └─────────────────────────────┘
  ┌──────────────────────────────┐  ┌─────────────────────────────┐
  │ tapaskar/pratibmb-aur        │  │ pratibmb.com (GitHub Pages) │
  │ yay -S pratibmb-bin          │  │ landing page + direct DLs   │
  │ auto-updated PKGBUILD        │  │ auto-deployed from site/    │
  └──────────────────────────────┘  └─────────────────────────────┘

  Build Matrix:
  ┌─────────────────┬──────────────────────┬──────────────────────┐
  │ macOS ARM (.dmg) │ macOS Intel (.dmg)   │ cross-compiled from  │
  │ macos-latest     │ macos-latest         │ ARM runner           │
  ├─────────────────┼──────────────────────┼──────────────────────┤
  │ Linux (.deb,     │ Windows (.exe, .msi) │                      │
  │  .AppImage)      │ windows-latest       │                      │
  │ ubuntu-22.04     │                      │                      │
  └─────────────────┴──────────────────────┴──────────────────────┘
```

## Model Selection

Selected after:
1. A **blind manual eval** of 6 candidates (Llama-3.2-3B, Llama-3.1-8B, Mistral-7B, Qwen2.5-7B, Gemma-3-4B, Gemma-2-9B) on a 10-prompt test set.
2. An **automated head-to-head** of the top contender vs Gemma-4-E4B, judged by Qwen2.5-7B with A/B position randomization.

Winner: **Gemma-3-4B-Instruct Q4_K_M** (2.32 GB, fastest of the top tier, wins on voice / grounding / emotion / style against every other candidate including newer models).

Full results in `docs/MODEL_EVAL.md`.

## Components

### `pratibmb.models` (auto-download)
On first launch, downloads pre-quantized GGUF files from HuggingFace Hub:
- Chat: `bartowski/google_gemma-3-4b-it-GGUF` → Q4_K_M (2.49 GB)
- Embed: `nomic-ai/nomic-embed-text-v1.5-GGUF` → Q4_K_M (84 MB)

Files cached at `~/.pratibmb/models/`. No auth required. Works offline after first download.

### `pratibmb.schema`
A single `Message` dataclass. Every importer emits these. Source-agnostic by design.

### `pratibmb.importers`
Pluggable importer layer. A new source = one new file implementing `Importer`. The protocol is tiny: `name`, `detect(path)`, `load(path, self_name)`. Importers stream — they never load an entire export into memory.

8 importers:
- `whatsapp.py` — iOS/Android "Export Chat" `.txt`
- `facebook.py` — Facebook DYI JSON (Messenger threads + posts)
- `instagram.py` — Instagram DYI JSON (DMs + posts)
- `gmail.py` — Google Takeout MBOX
- `imessage.py` — macOS `chat.db` (SQLite)
- `telegram.py` — Telegram Desktop JSON export
- `twitter.py` — Twitter/X archive (`.js` files)
- `discord.py` — DiscordChatExporter JSON

### `pratibmb.store.sqlite`
Flat SQLite schema: `messages`, `embeddings`, `profile`, `meta`. Embeddings are float32 BLOBs. Brute-force cosine over 100k vectors is sub-100ms on M-series Macs.

### `pratibmb.rag`
`Embedder` wraps llama.cpp in embedding mode (GGUF embedding model — keeps the runtime stack 100% llama.cpp, no Python ML deps in the shipped binary).
`Retriever` does year-filtered cosine search over `author = 'self'` only — we want past-you's voice, not what other people said. Each retrieved message expands to ±3 surrounding messages from the same thread for context.

### `pratibmb.profile`
Batch-analyzes the corpus with Gemma-3-4B to extract structured identity:
- Relationships (name, type, topics)
- Life events per year
- Year summaries
- Communication style

Profile stored as JSON in SQLite. Context builder assembles a ~200-token year-specific identity block for each chat turn.

### `pratibmb.voice`
Deterministic one-pass fingerprint of the user's own writing: lowercase ratio, typical message length, favorite phrases, emoji use, language mix. Rendered into a style directive injected into the system prompt.

### `pratibmb.llm`
`Chatter` wraps llama.cpp for chat generation. System prompt locks the model into "you are the user in year Y" and forbids assistant-speak. Optional LoRA adapter loaded at init time via `lora_path` parameter.

### `pratibmb.finetune`
Complete LoRA fine-tuning pipeline:
- `pairs.py` — Extract (other→self) conversation pairs from corpus
- `format.py` — Format into Gemma chat template
- `train.py` — Train via MLX-LM (macOS) or PyTorch+PEFT (Windows/Linux)
- `convert.py` — Convert adapter to GGUF format

### `pratibmb.server`
Stdlib HTTP server (no Flask/FastAPI) spawned by Tauri as sidecar. Binds to 127.0.0.1:11435 only. All endpoints are POST/GET JSON.

### `pratibmb.cli`
Click-based CLI: `init`, `import`, `embed`, `voice`, `chat`, `stats`.

## License

Dual-licensed: AGPLv3 for open use. Commercial licenses available for proprietary products. Contact admin@sparkupcloud.com.
