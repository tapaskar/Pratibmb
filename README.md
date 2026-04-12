# Pratibmb

**Chat with your 10-years-younger self. 100% local. No cloud. No telemetry.**

Pratibmb ingests your personal messaging history, builds a private corpus on your machine, and lets you have a conversation with the person who sent those messages years ago. A local LLM learns your voice, your relationships, your life events — and responds as past-you. Everything runs offline. Your data never leaves your computer.

> _Pratibmb_ is a coined word — a distinctive mark for a distinctive idea.

**[Download](https://pratibmb.com/#downloads)** | **[Documentation](./docs/HELP.md)** | **[Website](https://pratibmb.com)**

---

## Why

The most intimate data you own — a decade of private messages — is the one dataset you should never upload to somebody else's API. Pratibmb is built on a single non-negotiable: **run with the Wi-Fi off**.

## How it works

1. **Import** your chat exports from 8 supported platforms. Messages are parsed and stored in a local SQLite database.
2. **Embed** the corpus locally using a GGUF embedding model (84MB) via `llama.cpp`. No text leaves your device.
3. **Profile** — a local LLM (2.3GB) analyzes your conversations to extract relationships, life events, interests, and communication style.
4. **Chat** — pick a year on the slider and start texting past-you. Responses are grounded in your real memories and written in your voice.

Optional **LoRA fine-tuning** teaches the model your specific texting style — abbreviations, language mix, emoji patterns.

## Supported platforms

| Platform | Format | How to export |
|----------|--------|---------------|
| **WhatsApp** | `.txt` export | Menu > More > Export Chat (without media) |
| **Facebook** | JSON (DYI) | [facebook.com/dyi](https://facebook.com/dyi) > JSON format > Messages |
| **Instagram** | JSON (DYI) | Settings > Download Your Information > JSON > Messages |
| **Gmail** | MBOX (Takeout) | [takeout.google.com](https://takeout.google.com) > Mail |
| **iMessage** | `chat.db` (SQLite) | `~/Library/Messages/chat.db` (macOS, Full Disk Access required) |
| **Telegram** | JSON export | Desktop > Settings > Advanced > Export Telegram data > JSON |
| **Twitter / X** | Archive (`.js`) | Settings > Your Account > Download an archive |
| **Discord** | JSON ([DiscordChatExporter](https://github.com/Tyrrrz/DiscordChatExporter)) | Export channels/DMs as JSON |

Auto-detection: drop any supported file or folder into the app and Pratibmb figures out the format.

## Quick Install

```bash
# macOS / Linux
curl -fsSL https://pratibmb.com/install.sh | bash

# Windows (PowerShell)
irm https://pratibmb.com/install.ps1 | iex
```

This installs the desktop app, Python package, and all dependencies in one command.

## Download

Or download the desktop app manually:

| Platform | Download |
|----------|----------|
| macOS (Apple Silicon) | [.dmg (arm64)](https://github.com/tapaskar/Pratibmb/releases/latest/download/Pratibmb_0.5.0_aarch64.dmg) |
| macOS (Intel) | [.dmg (x64)](https://github.com/tapaskar/Pratibmb/releases/latest/download/Pratibmb_0.5.0_x64.dmg) |
| Linux | [.deb (amd64)](https://github.com/tapaskar/Pratibmb/releases/latest/download/Pratibmb_0.5.0_amd64.deb) / [.AppImage](https://github.com/tapaskar/Pratibmb/releases/latest/download/Pratibmb_0.5.0_amd64.AppImage) |
| Windows | [.exe installer](https://github.com/tapaskar/Pratibmb/releases/latest/download/Pratibmb_0.5.0_x64-setup.exe) / [.msi](https://github.com/tapaskar/Pratibmb/releases/latest/download/Pratibmb_0.5.0_x64_en-US.msi) |

Requires Python 3.9+ and ~8GB RAM. Models (~2.5GB) are downloaded on first launch.

> **macOS users:** If you see "Pratibmb is damaged and can't be opened", run:
> ```bash
> xattr -cr /Applications/Pratibmb.app
> ```
> This removes the macOS quarantine flag on unsigned apps. The app is open source — [verify the code yourself](https://github.com/tapaskar/Pratibmb).

## Installation from source

```bash
# Clone
git clone https://github.com/tapaskar/Pratibmb.git
cd Pratibmb

# Install (Python package)
pip install -e .

# Run CLI
pratibmb --help

# Or run the desktop app
cd desktop && npm install && cargo tauri dev
```

## Fine-tuning

Optional LoRA training makes past-you sound even more authentic. Pratibmb auto-detects your platform:

| Platform | Backend | GPU? | Time (~1500 pairs) | Install |
|----------|---------|------|---------------------|---------|
| macOS (Apple Silicon) | MLX-LM | No (Metal) | ~20 min | `pip install mlx-lm` |
| Windows / Linux (NVIDIA) | PyTorch + QLoRA | Yes (6GB+ VRAM) | ~30 min | `pip install 'pratibmb[finetune-pytorch]'` |
| Linux (CPU-only) | PyTorch | No | ~2 hours | `pip install 'pratibmb[finetune-pytorch]'` |

Fine-tuning is accessible from the gear icon in the desktop app or via `pratibmb finetune train` on the CLI.

## Privacy by architecture

- **100% local.** Every computation runs on your hardware. Messages, embeddings, models, and profiles never leave your machine.
- **No cloud.** No OpenAI API, no cloud inference, no remote servers. Works with Wi-Fi off after the initial model download.
- **No telemetry.** Zero analytics, no crash reports, no usage tracking, no phone-home.
- **Open source.** Every line is auditable. Don't trust us — verify.

## Why Gemma-3-4B

Selected after a blind evaluation of 6 candidate models and a head-to-head vs Gemma-4-E4B, judged by an impartial different-family model. Full results in [`docs/MODEL_EVAL.md`](./docs/MODEL_EVAL.md).

## License

**Dual-licensed.**

- **Open source** — [AGPLv3](./LICENSE). Free to use, study, modify, and self-host. If you run a modified version as a hosted service, you must share your changes under the same license.
- **Commercial** — Companies that cannot comply with AGPL (e.g., proprietary SaaS, embedding in closed-source products, or distributing without source disclosure) can purchase a commercial license. Contact **admin@sparkupcloud.com** for terms.

This dual-license model keeps Pratibmb free for individuals, researchers, and open-source projects, while ensuring that commercial use contributes back — either in code or in funding.

## Contributing

A CLA (Contributor License Agreement) is required for all contributions. This allows the project to offer commercial licenses without needing permission from every contributor. See `CONTRIBUTING.md` for details.

## Safety

Pratibmb is not therapy. If you use it to process grief, set time limits, and speak to a professional. Built-in session limits and gentle reframes are part of the v1 roadmap.
