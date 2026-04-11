# Hacker News — Show HN Post

## Title

Show HN: Pratibmb – Chat with your past self using your real messaging history (100% local)

## Link

https://pratibmb.com

## First Comment (post immediately after submitting)

---

Hi HN, I built Pratibmb — a desktop app that lets you chat with your 10-years-younger self using your actual messaging history.

**How it works:**

1. Export your chats from any of 8 platforms (WhatsApp, Facebook, Instagram, Gmail, iMessage, Telegram, Twitter/X, Discord)
2. Drop the export into the app — it auto-detects the format and builds a local SQLite corpus
3. A local embedding model (Nomic Embed, 84MB) creates semantic vectors for retrieval
4. A local LLM (Gemma-3-4B, 2.3GB GGUF via llama.cpp) generates responses grounded in your real messages
5. Pick a year on the slider, ask a question, and past-you responds in your voice

**Optional LoRA fine-tuning** on Apple Silicon (MLX, ~20 min) or NVIDIA GPUs (PyTorch/QLoRA, ~30 min) makes it sound even more like you.

**The privacy argument:** Your decade of private messages is the one dataset you should never upload to someone else's API. Everything runs offline after a one-time 2.5GB model download. No cloud, no API keys, no telemetry, no accounts. Check the source: it's all there.

**Tech stack:**
- Tauri 2 (Rust + WebView) for the desktop shell
- Python sidecar for the AI pipeline
- llama-cpp-python for GGUF inference
- Nomic Embed v1.5 for semantic retrieval
- Gemma-3-4B-Instruct for chat generation
- MLX-LM / PyTorch for LoRA fine-tuning
- Pure vanilla HTML/CSS/JS for the UI (zero npm dependencies)

**What surprised me:** How differently I texted in 2014 vs now. More exclamation marks, more emoji, completely different slang. The model picked up on patterns I'd forgotten about.

Available for macOS (Apple Silicon + Intel), Linux (.deb, .AppImage), and Windows (.exe, .msi). AGPLv3 — free for personal use, commercial license required for business use.

Would love feedback on the RAG pipeline, the fine-tuning approach, or the general UX. Happy to answer questions about the architecture.

---

## Timing

Post between 9-10am ET on a Tuesday or Wednesday.
Stay online ALL DAY to respond to every comment.

## Likely Questions & Answers

**Q: "Is this therapy?"**
A: No, and I'm careful about that. The README and app both say this explicitly. Built-in session limits and gentle reframes are on the v1 roadmap. If someone is processing grief, I recommend professional support.

**Q: "What about hallucinations?"**
A: The RAG pipeline grounds every response in actual retrieved messages. It can still hallucinate details, but the thread-context expansion (showing surrounding messages) helps keep it anchored. Fine-tuning improves accuracy further.

**Q: "Why not just use ChatGPT?"**
A: Because I'd have to upload my most intimate data to OpenAI's servers. That's exactly the trade-off I built this to avoid.

**Q: "Why Gemma-3-4B?"**
A: Blind evaluation of 6 models, judged by an impartial different-family model. Full results in docs/MODEL_EVAL.md. Gemma-3-4B won on voice authenticity, instruction following, and emotional nuance.

**Q: "Python sidecar seems hacky"**
A: Pragmatic choice. The ML ecosystem (llama.cpp bindings, MLX, PyTorch) is Python-native. Tauri handles the UI + process lifecycle, Python handles the AI. They communicate via localhost HTTP. It works well in practice.
