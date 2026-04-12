# I Built an App That Lets You Chat With Your Past Self

*Cross-post to: your blog at pratibmb.com/blog, Dev.to, Medium (Towards Data Science)*

---

## What would you say to who you were 10 years ago?

I've been thinking about this question for a while. Not in a hypothetical, motivational-poster way — but literally. What if you could text the person you were in 2014 and get a response in their voice, grounded in their actual life?

That's what I built. It's called **Pratibmb**, and it runs entirely on your machine.

## The idea

Your messaging history is a time capsule. Thousands of conversations across WhatsApp, Facebook, Instagram, Gmail, iMessage, Telegram, Twitter, and Discord — they contain a version of you that no longer exists. The way you talked, the things you cared about, the jokes you made, the people you loved.

Modern LLMs are surprisingly good at learning someone's communication style from examples. Combine that with retrieval-augmented generation (pulling relevant past messages for context), and you get something that feels startlingly real.

But there's a catch: your messaging history is the most intimate data you own. I wasn't willing to upload mine to anyone's API.

## The privacy problem

Every "AI assistant" service requires sending your data to the cloud. ChatGPT, Claude, Gemini — they all need your text on their servers to process it. For most use cases, that's fine. For a decade of private messages? No.

I built Pratibmb with a single non-negotiable: **run with the Wi-Fi off.**

After a one-time model download (~2.5GB from HuggingFace), the entire pipeline runs locally:

- **Embedding:** Nomic Embed Text v1.5 (84MB GGUF) creates semantic vectors of your messages
- **Retrieval:** Year-filtered cosine similarity with thread-context expansion
- **Generation:** Gemma-3-4B-Instruct (2.3GB GGUF) via llama.cpp
- **Fine-tuning:** Optional LoRA training via MLX (Apple Silicon) or PyTorch (NVIDIA)

No API calls. No cloud inference. No telemetry. No accounts.

## How it works

1. **Import** — Export your chats from any of 8 platforms. Drop the file into the app. Pratibmb auto-detects the format (WhatsApp .txt, Facebook JSON, Gmail MBOX, iMessage SQLite, etc.) and builds a local corpus.

2. **Embed** — A local embedding model creates semantic representations of your messages. This takes 5-15 minutes depending on corpus size, all on your CPU/GPU.

3. **Profile** — The LLM analyzes your conversations to extract relationships, life events, interests, and communication style. This produces a structured profile that grounds future responses.

4. **Chat** — Pick a year on the slider and start texting. The app retrieves semantically similar messages from that era, expands them with surrounding thread context, and generates a response in your voice.

## The technical details (for the curious)

### RAG with thread context

Naive RAG retrieves isolated messages — fragments that lack conversational flow. I added **thread-context expansion**: when a message is retrieved, the surrounding messages (typically 3 before and 3 after) are included too. This lets the LLM see the full conversation arc, not just a sentence.

### Year-filtered retrieval

The year slider isn't just a UI gimmick. The embedding search is filtered to only retrieve messages from before the selected year. Ask 2016-you about something that happened in 2018, and they genuinely won't know about it.

### LoRA fine-tuning

The base model (Gemma-3-4B) already does a decent job with RAG alone. But fine-tuning on your actual message pairs makes it sound remarkably more like you. The pipeline:

1. **Extract** — Automatically creates instruction-following pairs from your conversations (your message as the expected response, the preceding context as the prompt)
2. **Train** — LoRA fine-tuning with MLX on Apple Silicon (~20 min) or PyTorch/QLoRA on NVIDIA (~30 min)
3. **Convert** — Merges the adapter into a GGUF file for inference

On my MacBook Pro M2, fine-tuning on 1500 message pairs takes about 20 minutes and makes a noticeable difference in voice authenticity.

### Why Gemma-3-4B?

I ran a blind evaluation of 6 candidate models (Llama-3.2-3B, Mistral-7B, Phi-3-mini, Qwen-2.5-3B, Gemma-2-2B, Gemma-3-4B), judged by an impartial different-family model on voice authenticity, instruction following, and emotional nuance. Gemma-3-4B won. Full results are in the repo at `docs/MODEL_EVAL.md`.

### The desktop app

The app is built with **Tauri 2** (Rust backend + WebView frontend). The Rust side spawns a Python sidecar process that runs the AI pipeline on `127.0.0.1:11435`. The frontend is plain HTML/CSS/JS — zero npm dependencies, zero build step.

Why this architecture? The ML ecosystem (llama.cpp bindings, MLX, PyTorch, transformers) is Python-native. Tauri handles the native desktop experience (window management, file dialogs, process lifecycle). They communicate via localhost HTTP. It's pragmatic and it works.

## What surprised me

**How differently I texted in 2014.** More exclamation marks. More emoji. Different slang. A completely different sense of humor. The model picked up on patterns I'd genuinely forgotten about — phrases I used to use, topics I cared about, even the way I structured sentences.

**How emotional it can be.** Chatting with "past-me" about old friendships and relationships was unexpectedly moving. Not because the model is perfect — it's clearly an AI — but because it's grounded in real memories. It surfaces things you've forgotten. I added a disclaimer in the app: "This is not therapy. If you use it to process grief, set time limits and speak to a professional."

**How well RAG works for personal data.** LLMs trained on the internet don't know about your life. But give them your actual messages as context, and they can generate responses that feel grounded in a way that generic chatbots never do. The combination of retrieval + fine-tuning is more powerful than either alone.

## Try it

Pratibmb is free for personal use, open source (AGPLv3), and available for macOS (Apple Silicon + Intel), Linux (.deb, .AppImage), and Windows (.exe, .msi).

- **Website:** [pratibmb.com](https://pratibmb.com)
- **GitHub:** [github.com/tapaskar/Pratibmb](https://github.com/tapaskar/Pratibmb)
- **Download:** [pratibmb.com/#downloads](https://pratibmb.com/#downloads)

Models auto-download on first launch. You need Python 3.9+ and about 4GB of RAM.

If you've ever wondered what you'd say to who you were 10 years ago — now you can try it.

---

*Pratibmb is AGPLv3 for personal use. Commercial use requires a separate license. Contact admin@sparkupcloud.com for terms.*
