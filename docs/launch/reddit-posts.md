# Reddit Launch Posts

Post these 2-3 hours apart on the same day as HN. Respond to every comment.

---

## r/LocalLLaMA

**Title:** I built a RAG + LoRA fine-tuning app that learns your texting style from WhatsApp/iMessage exports. Runs 100% offline with Gemma-3-4B.

**Body:**

I've been working on Pratibmb — a desktop app that ingests your personal messaging history and lets you "chat with your past self."

**How it works:**

- Import chat exports from 8 platforms (WhatsApp, Facebook, Instagram, Gmail, iMessage, Telegram, Twitter/X, Discord)
- Nomic Embed Text v1.5 (84MB, Q4_K_M GGUF) creates semantic embeddings of your messages
- Year-filtered RAG retrieves relevant messages with thread-context expansion (surrounding messages for conversation flow)
- Gemma-3-4B-Instruct (2.3GB, Q4_K_M GGUF) generates responses grounded in your actual messages
- All inference via llama-cpp-python

**Fine-tuning:**

- MLX-LM LoRA on Apple Silicon (~20 min for 1500 pairs)
- PyTorch + QLoRA on NVIDIA (~30 min, 6GB+ VRAM)
- Extracts instruction-following pairs from your conversations automatically
- The model learns your abbreviations, language mixing, emoji patterns, sentence structure

**Why Gemma-3-4B?** Blind evaluation of 6 candidates (Llama, Mistral, Phi, Qwen, Gemma-2, Gemma-3), judged by an impartial different-family model. Full results in the repo: docs/MODEL_EVAL.md

**Stack:** Tauri 2 (Rust + WebView) desktop shell, Python sidecar for AI, vanilla HTML/CSS/JS UI (zero npm deps). Models auto-download from HuggingFace on first launch.

Free for personal use (AGPLv3). Available for macOS, Linux, Windows.

- Website: [pratibmb.com](https://pratibmb.com)
- GitHub: [github.com/tapaskar/Pratibmb](https://github.com/tapaskar/Pratibmb)

Happy to discuss the RAG pipeline, quantization choices, or fine-tuning approach.

---

## r/selfhosted

**Title:** Pratibmb: Chat with your past self using your real messaging history. 100% local, no cloud, no API keys, no telemetry.

**Body:**

Built a desktop app that lets you import your messaging history from 8 platforms (WhatsApp, Facebook, Instagram, Gmail, iMessage, Telegram, Twitter/X, Discord) and "chat" with the person you were years ago.

**Privacy-first by design:**

- Everything runs on your machine. No cloud servers, no API calls, no accounts
- Works fully offline after a one-time 2.5GB model download
- Zero telemetry — no analytics, no crash reports, no phone-home
- Data stored in local SQLite + numpy arrays in `~/.pratibmb/`
- Open source (AGPLv3) — every line is auditable

**How it works:**

1. Export your chats and drop them into the app
2. A local embedding model (84MB) indexes your messages semantically
3. A local LLM (2.3GB, Gemma-3-4B) generates responses in your voice
4. Pick a year and start chatting — past-you responds using your real memories

Optional LoRA fine-tuning teaches the model your exact texting style.

**Self-hosting:** It's a desktop app (Tauri 2), not a web service. Install, run, done. No Docker, no config files, no port forwarding. Models auto-download from HuggingFace on first launch.

Available for macOS, Linux (.deb, .AppImage), and Windows (.exe, .msi).

Website: [pratibmb.com](https://pratibmb.com)
GitHub: [github.com/tapaskar/Pratibmb](https://github.com/tapaskar/Pratibmb)

---

## r/privacy

**Title:** I built a "chat with your past self" app that processes your most intimate data (messaging history) without any cloud, API, or telemetry

**Body:**

Your messaging history — decades of private conversations — is arguably the most intimate data you own. Every "chat with AI" service requires uploading it to someone else's servers.

I built Pratibmb to solve this: it runs 100% locally on your machine.

**What it does:** Import your chats from WhatsApp, Facebook, Instagram, Gmail, iMessage, Telegram, Twitter/X, or Discord. A local AI learns your communication style and lets you "text your past self."

**Privacy architecture (not just policy):**

- All computation runs on your hardware (CPU/GPU)
- No network calls after the initial model download (~2.5GB, from HuggingFace)
- No accounts, no login, no cloud storage
- Zero telemetry: no analytics, no crash reports, no phone-home
- Data stored in local files (`~/.pratibmb/`), not a cloud database
- Open source (AGPLv3): every line auditable on GitHub
- The landing page itself has no cookies, no tracking pixels, no external requests

**What it doesn't do:**

- No OpenAI/Anthropic/Google API calls
- No data leaves your machine (verify yourself in the source)
- No "anonymous" usage statistics
- No account creation or email collection

This is the kind of application where privacy isn't a feature — it's the reason the product exists.

Website: [pratibmb.com](https://pratibmb.com)
GitHub: [github.com/tapaskar/Pratibmb](https://github.com/tapaskar/Pratibmb)

---

## r/opensource

**Title:** Pratibmb: Open-source desktop app to chat with your past self using your messaging history. AGPLv3, local-only, no telemetry.

**Body:**

Sharing a project I've been working on — Pratibmb lets you import your messaging history from 8 platforms and chat with the person you were years ago, using a local LLM.

**License:** AGPLv3 — free for individuals, researchers, and open-source projects. Commercial use requires a separate license.

**Tech:** Tauri 2 (Rust/WebView), Python AI backend, Gemma-3-4B via llama.cpp, vanilla HTML/CSS/JS (zero npm deps).

**Why open source:** The app processes your most private data. You should be able to audit every line. Open source isn't optional for this kind of tool — it's a requirement.

GitHub: [github.com/tapaskar/Pratibmb](https://github.com/tapaskar/Pratibmb)
Website: [pratibmb.com](https://pratibmb.com)

---

## Timing

1. r/LocalLLaMA — 30 min after HN post
2. r/selfhosted — 2 hours after HN
3. r/privacy — 3 hours after HN
4. r/opensource — 4 hours after HN (or next day)
