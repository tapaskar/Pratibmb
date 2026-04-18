---
title: I built an app that lets you chat with your past self — using your real messages
published: true
description: Your old WhatsApp, Facebook, and Instagram messages contain a version of you that doesn't exist anymore. I built a desktop app that brings them back. 100% local. No cloud. No API keys.
tags: opensource, ai, privacy, showdev
cover_image: https://raw.githubusercontent.com/tapaskar/Pratibmb/main/docs/launch/devto-cover.png
canonical_url: https://pratibmb.com/blog/chat-with-your-past-self
---

I texted my 22-year-old self last night.

He told me about a hackathon project I'd completely forgotten. He used slang I haven't used in years. He was worried about things that don't matter anymore — and passionate about things I've since abandoned.

He wasn't an AI pretending to be me. He *was* me — reconstructed from 47,000 real messages I'd sent between 2014 and 2018.

This is **Pratibmb**.

![Pratibmb chat interface showing a conversation with your past self](https://raw.githubusercontent.com/tapaskar/Pratibmb/main/docs/screenshots/01_chat_ready.png)

---

## The idea

I was cleaning up my phone storage and found a WhatsApp export from college. Reading through those messages was surreal. The person writing them was recognizably me — same humor, same anxieties — but also someone I'd never be again.

I thought: *what if I could actually talk to that version of myself?*

Not a generic chatbot. Not "based on your journal entries." I wanted something that had read every message I'd ever sent and could respond the way I actually used to talk — the exact slang, the emoji patterns, the way I'd dodge serious questions with a joke.

So I built it.

---

## How it works

Pratibmb is a 4-step pipeline that runs entirely on your machine:

### 1. Import your messages

Export your chat history from any of 8 platforms:

- **WhatsApp** — plain text export
- **Facebook Messenger** — JSON from Download Your Information
- **Instagram DMs** — JSON from Download Your Information
- **Gmail** — MBOX from Google Takeout
- **iMessage** — reads the local `chat.db` directly
- **Telegram** — JSON export from Desktop app
- **Twitter / X** — JavaScript archive
- **Discord** — JSON via DiscordChatExporter

The app auto-detects the format. Drop the file, it figures out the rest.

### 2. Embed everything locally

Every message gets converted into a semantic vector using [Nomic Embed Text v1.5](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5-GGUF) (84 MB model, runs via llama.cpp). These embeddings are stored in a local SQLite database — no vector database dependency, no Pinecone, no cloud.

### 3. Build your profile

A local LLM ([Gemma 3 4B Instruct](https://huggingface.co/bartowski/google_gemma-3-4b-it-GGUF), quantized to 2.5 GB) analyzes your message corpus and extracts:

- **Relationships** — who you talked to, how close you were, what you discussed
- **Life events** — career changes, moves, breakups, milestones (with confidence scores)
- **Interests** — what you cared about and when
- **Communication style** — your abbreviations, emoji habits, sentence patterns
- **Year summaries** — what each year of your life looked like through your messages

This profile grounds the AI's responses in your actual history.

### 4. Chat with your past self

Pick a year on the slider. Ask a question. The app retrieves relevant messages from that time period using semantic search, feeds them as context to the LLM along with your profile, and generates a response in your voice.

```
You: what were my biggest dreams in college?

Pratibmb (2018): oh man, where do I start! I was convinced 
I'd build the next big startup — something that would change 
how people connect. the biggest dream was proving to myself 
I could make something people actually used.
```

The year slider is the key interaction — slide to 2015 and you're talking to your 2015 self. Slide to 2020 and the responses shift to match who you were then.

---

## The tech stack

I wanted this to be something anyone could run without cloud accounts or GPU rentals:

| Layer | Tech | Why |
|-------|------|-----|
| Desktop shell | **Tauri 2** (Rust) | ~5 MB binary vs 150 MB Electron, native performance |
| AI inference | **llama.cpp** via llama-cpp-python | Runs quantized models on CPU or Metal/CUDA |
| Chat model | **Gemma 3 4B Q4_K_M** | Strong instruction-following at only 2.5 GB |
| Embeddings | **Nomic Embed Text v1.5 Q4_K_M** | 84 MB, fast cosine similarity search |
| Storage | **SQLite** | Zero-config, single-file, no server |
| Frontend | **Vanilla HTML/CSS/JS** | No build step, no framework churn |
| Fine-tuning | **LoRA** via MLX (macOS) or PyTorch+PEFT (Linux/Windows) | Optional, makes responses sound more like you |

### Architecture

```
┌─────────────────────────────────┐
│  Tauri webview (HTML/JS)        │
│  Year slider + chat interface   │
└──────────────┬──────────────────┘
               │ Tauri commands
               ▼
┌─────────────────────────────────┐
│  Rust backend                   │
│  - Spawns llama-server process  │
│  - Owns SQLite corpus           │
│  - Streams replies to webview   │
└──────────────┬──────────────────┘
               │ HTTP (localhost:11435)
               ▼
         llama-server
    (Gemma 3 4B + Nomic Embed)
```

No Docker. No Redis. No Postgres. One binary that spawns a local inference server and talks to it over localhost.

---

## The hardest problems I solved

### Making a 4B model sound like a specific person

Generic LLMs sound like... generic LLMs. Even with good retrieval, the responses felt artificial. Three things fixed this:

**1. Aggressive post-processing.** I strip markdown formatting, remove AI-isms ("As an AI...", "Here's what I think..."), truncate to 6 sentences max, and remove surrounding quotes. Real text messages are short and messy.

**2. Profile-grounded system prompt.** The system prompt doesn't just say "act like this person" — it includes extracted communication patterns: typical sentence length, favorite slang, emoji frequency, how they handle serious vs. casual questions.

**3. Optional LoRA fine-tuning.** The app extracts conversation pairs from your messages and fine-tunes a LoRA adapter (rank 8, alpha 16) on your actual writing patterns. ~20 minutes on Apple Silicon, ~30 on NVIDIA. This is optional but makes a noticeable difference — responses shift from "plausible generic" to "that's actually how I talk."

### Thread-context retrieval

Naive RAG retrieves individual messages, but conversations have context. If you ask "what did I think about moving to Bangalore?", the most relevant message might be "yeah I'm really nervous about it" — meaningless without the preceding messages.

The retriever expands each hit to include surrounding messages in the same thread (3-message window), then groups them chronologically. The LLM sees conversation fragments, not isolated sentences.

### SQLite + threading in a desktop app

Tauri's async Rust backend and Python's threaded HTTP server both want to touch the database. SQLite doesn't love concurrent writes. I solved this with:

- `check_same_thread=False` on the Python connection
- A threading `Lock` around all write operations
- WAL mode for better concurrent read performance

Simple, but it took a few crashes to get right.

---

## Privacy — not as a feature, as the architecture

I'm tired of apps that say "we take your privacy seriously" and then ship your data to 14 third-party services.

Pratibmb can't leak your data because it never has your data. The architecture makes privacy violations impossible, not just policy-prohibited:

- **No network calls** after the initial model download (~2.5 GB, one time)
- **No telemetry.** No analytics. No crash reports. No "anonymous" usage data.
- **No accounts.** No login. No email. Nothing.
- **Works with Wi-Fi off.** Literally turn off your internet after setup. Everything works.
- **Open source** (AGPL-3.0). Read every line. Build from source. Audit the network calls (there are none).

Your messages, embeddings, profile, and fine-tuned model all live in `~/.pratibmb/` on your machine. Delete the folder and it's gone.

---

## What I learned building this

**1. Small models are good enough for personal use.**
Gemma 3 4B quantized to Q4_K_M runs comfortably on 8 GB RAM and produces surprisingly good responses when you give it strong retrieval context. You don't need GPT-4 for everything.

**2. Tauri is genuinely great.**
Coming from Electron, the difference is staggering. 5 MB binary. Instant startup. Native file dialogs. The Rust ↔ JS bridge is clean. The only pain point is the build toolchain on Windows (MSVC + WebView2 + NSIS).

**3. The emotional impact surprised me.**
I built this as a technical project. But the first time I asked my 2016 self about a friend I'd lost touch with, and it responded with details I'd forgotten — I sat there for a while. This thing surfaces memories that photos can't.

**4. Chat exports are a mess.**
WhatsApp's export format changes between OS versions. Facebook's JSON uses UTF-8 escape sequences for emoji. iMessage requires Full Disk Access and the database schema varies across macOS versions. Telegram only exports from the desktop app. I wrote 8 parsers and each one taught me something new about format hell.

---

## Try it

Pratibmb is free, open source, and runs on macOS, Windows, and Linux.

🔗 **Website:** [pratibmb.com](https://pratibmb.com)
📦 **GitHub:** [github.com/tapaskar/Pratibmb](https://github.com/tapaskar/Pratibmb)

**Requirements:**
- macOS 12+ / Windows 10+ / Linux (AppImage)
- Python 3.10+
- 8 GB RAM (16 GB recommended)
- ~3 GB disk space for models (downloaded on first launch)
- NVIDIA GPU optional (speeds up fine-tuning, not required for chat)

**Install:**

```bash
# macOS
brew install tapaskar/tap/pratibmb

# Linux (AUR)
yay -S pratibmb-bin

# Windows
winget install tapaskar.Pratibmb

# Or download directly from pratibmb.com
```

---

## What's next

- **v0.6.0** — Voice mode (talk to your past self, hear responses in a synthesized version of your voice)
- **Group chat reconstruction** — Bring back entire friend groups, not just yourself
- **Timeline view** — Visual map of your relationships and life events across years
- **Mobile app** — React Native wrapper (local inference via llama.cpp on-device)

If you have old messages sitting on your phone or in a Google Takeout archive — they contain a version of you that doesn't exist anymore. Pratibmb brings them back.

---

*If you try it, I'd love to hear what your past self had to say. Drop a comment or find me on [GitHub](https://github.com/tapaskar/Pratibmb).*
