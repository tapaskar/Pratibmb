# Pratibmb

**Chat with your 10-years-younger self. 100% local. No cloud. No telemetry.**

Pratibmb ingests your personal history — WhatsApp, Facebook, Instagram, Gmail, and more — builds a private corpus on your machine, and lets you have a conversation with the person who sent those messages years ago. Everything runs locally on a quantized LLM. Your data never leaves your computer.

> _Pratibmb_ is a coined word — a distinctive mark for a distinctive idea.

## Why

The most intimate data you own — a decade of private messages — is the one dataset you should never upload to somebody else's API. Pratibmb is built on a single non-negotiable: **run with the Wi-Fi off**.

## Status

Pre-alpha. Actively being built in the open. Follow the [build journal](./docs/JOURNAL.md) for weekly updates.

## How it works

1. **Import** your data exports (WhatsApp `.txt`, Facebook/Instagram DYI JSON, etc.) through pluggable importers that normalize everything to a single schema.
2. **Embed** the corpus locally using a GGUF embedding model via `llama.cpp`.
3. **Retrieve** time-filtered context for each prompt (year slider — talk to 2016-you, 2019-you, etc.).
4. **Generate** responses with Gemma-3-4B-Instruct running locally via `llama.cpp`, prompted to match the voice and tone of the retrieved past messages.

## Why Gemma-3-4B

Selected after a blind evaluation of 6 candidate models and a head-to-head vs Gemma-4-E4B, judged by an impartial different-family model. Full results in [`docs/MODEL_EVAL.md`](./docs/MODEL_EVAL.md).

## License

AGPLv3. You are free to use, study, modify, and self-host Pratibmb. If you run it as a hosted service, you must share your modifications back. Paid, signed, notarized desktop builds with premium importers and support are sold separately — the open-core model.

## Contributing

A CLA is required so the project can be dual-licensed to companies later. See `CONTRIBUTING.md` (coming soon).

## Safety

Pratibmb is not therapy. If you use it to process grief, set time limits, and speak to a professional. Built-in session limits and gentle reframes are part of the v1 roadmap.
