# Pratibmb Help Guide

Chat with your 10-years-younger self. 100% local.

---

## Getting Started

1. **Install** the desktop app from [pratibmb.com](https://pratibmb.com) or build from source
2. **Launch** the app. On first run, the onboarding wizard guides you through setup
3. **Enter your name** as it appears in your chat exports (e.g., "Tapas Kar")
4. **Import** at least one chat export (see platform guides below)
5. **Build index** (the app does this automatically)
6. **Chat** with past-you by picking a year and typing a message

### System Requirements

| | Minimum | Recommended |
|--|---------|-------------|
| RAM | 8 GB | 16 GB |
| Disk | 3 GB (for models) | 10 GB |
| Python | 3.9+ | 3.11+ |
| GPU | Not required | Apple Silicon or NVIDIA (6GB+ VRAM) for fine-tuning |

### Models

On first use, the app downloads two models:
- **nomic-embed-text-v1.5** (84 MB) — for semantic search
- **Gemma 3 4B Instruct** (2.3 GB) — for chat and profile extraction

Models are cached at `~/.pratibmb/models/` and never re-downloaded.

---

## Platform Guides

### WhatsApp

**Format:** `.txt` file (one per chat)

**How to export:**
1. Open any chat in WhatsApp (iOS or Android)
2. Tap the contact/group name at the top
3. Scroll down to **Export Chat**
4. Choose **Without Media** (faster, smaller)
5. Save the `.txt` file to your computer
6. Drag it into Pratibmb, or click the import button

**Tips:**
- Repeat for each chat you want to include
- Group chats work too
- Both iOS and Android export formats are supported
- Your name must match exactly how WhatsApp shows it

---

### Facebook / Messenger

**Format:** JSON (from Download Your Information)

**How to export:**
1. Go to [facebook.com/dyi](https://www.facebook.com/dyi)
2. Click **Request a download**
3. Select **JSON** format (not HTML)
4. Under "Your information", select **Messages** and/or **Posts**
5. Click **Create File** — Facebook emails you when ready (can take hours)
6. Download and **unzip** the archive
7. Point Pratibmb at the unzipped folder (e.g., `facebook-yourname-2024/`)

**Tips:**
- This is the richest source for pre-2015 data
- Posts, comments, and Messenger DMs are all imported
- Facebook double-encodes UTF-8 — Pratibmb fixes the mojibake automatically

---

### Instagram

**Format:** JSON (from Download Your Information)

**How to export:**
1. Go to [Instagram Settings > Download Your Information](https://www.instagram.com/download/request/)
2. Choose **JSON** format
3. Select **Messages** and/or **Posts**
4. Request download — Instagram emails you when ready
5. Unzip and point Pratibmb at the folder

**Tips:**
- DMs and posts are both imported
- Same mojibake issue as Facebook — handled automatically

---

### Gmail (Google Takeout)

**Format:** MBOX (from Google Takeout)

**How to export:**
1. Go to [takeout.google.com](https://takeout.google.com)
2. Click **Deselect all**
3. Scroll down and select only **Mail**
4. Click **Next step** > **Create export**
5. Wait for the download link (can take hours for large mailboxes)
6. Download and unzip
7. Point Pratibmb at the `.mbox` file or the `Takeout/Mail/` folder

**Tips:**
- Large mailboxes (10+ years) can be several GB — be patient
- Emails are threaded by `References` and `In-Reply-To` headers
- Your name is matched against the `From` header display name and email address
- Attachments are not imported (text only)

---

### iMessage (macOS only)

**Format:** SQLite database (`chat.db`)

**How to use:**
1. Open **System Settings** > **Privacy & Security** > **Full Disk Access**
2. Add your terminal app (Terminal.app or iTerm2) to the list
3. The iMessage database is at: `~/Library/Messages/chat.db`
4. Point Pratibmb at that file

**Tips:**
- macOS only — iMessage data is not accessible on Windows or Linux
- Quit the Messages app before importing for consistent reads
- Both SMS and iMessage conversations are included
- macOS Ventura+ changed the message storage format — Pratibmb handles both old and new formats
- Timestamps use Apple's epoch (2001-01-01) — converted automatically

---

### Telegram

**Format:** JSON (from Telegram Desktop)

**How to export:**
1. Open **Telegram Desktop** (not mobile)
2. Go to **Settings** > **Advanced** > **Export Telegram data**
3. Select the chats you want to export
4. Choose **Machine-readable JSON** format
5. Click **Export** — saves to a folder on your computer
6. Point Pratibmb at the export folder (contains `result.json`)

**Tips:**
- Mobile app does not have export functionality — must use Desktop
- Both private and group chats are supported
- Service messages (joined/left/pinned) are automatically filtered out
- Media references are noted but not imported

---

### Twitter / X

**Format:** JavaScript archive (`.js` files)

**How to export:**
1. Go to **Settings** > **Your Account** > **Download an archive of your data**
2. Confirm your identity
3. Wait 24-48 hours for the archive to be prepared
4. Download and unzip the archive
5. Point Pratibmb at the unzipped folder (contains `data/tweets.js`)

**Tips:**
- Both tweets and DMs are imported
- The archive uses a JavaScript wrapper around JSON — Pratibmb strips it automatically
- Your account ID is read from `data/account.js` to identify your messages in DMs
- Tweet timestamps use a special format — handled automatically

---

### Discord

**Format:** JSON (via DiscordChatExporter)

Discord does not provide an official export tool. Use the community tool:

**How to export:**
1. Download [DiscordChatExporter](https://github.com/Tyrrrz/DiscordChatExporter) (open source)
2. Get your Discord token (see DiscordChatExporter docs)
3. Select the channels/DMs you want to export
4. Choose **JSON** format
5. Export to a folder
6. Point Pratibmb at the JSON file or the export folder

**Tips:**
- Each channel exports as a separate JSON file
- Point at the folder to import all channels at once
- System messages (joins, pins, boosts) are automatically filtered
- Using personal account tokens may violate Discord ToS — use at your own risk

---

## Fine-Tuning Your Model

Fine-tuning is optional but makes past-you's replies significantly more authentic. It teaches the model your specific texting style (abbreviations, language mix, emoji patterns).

### Step 1: Extract Training Pairs

```bash
pratibmb finetune extract-pairs
```

This scans your conversations for natural reply-pairs (friend says X, you reply Y). Typically extracts 1,000-3,000 pairs.

### Step 2: Train

```bash
pratibmb finetune train
```

Trains a LoRA adapter on your conversation style. See platform-specific backends below.

### Step 3: Convert (if needed)

```bash
pratibmb finetune convert
```

Converts the adapter to GGUF format for llama.cpp inference. Restart the app to load the fine-tuned model.

### Platform-Specific Training

#### macOS (Apple Silicon)

Uses **MLX-LM** for native Metal GPU acceleration. Fastest option.

```bash
pip install mlx-lm
pratibmb finetune train
```

- ~20 minutes for 1,500 pairs on M1/M2/M3
- ~6GB RAM usage during training
- No NVIDIA GPU needed

#### Windows / Linux (NVIDIA GPU)

Uses **PyTorch + PEFT + QLoRA** with CUDA acceleration.

```bash
pip install "pratibmb[finetune-pytorch]"
pratibmb finetune train
```

- Requires NVIDIA GPU with 6GB+ VRAM
- ~30 minutes for 1,500 pairs
- Supports RTX 3060+ / RTX 4060+

#### Linux (CPU-only)

Works but significantly slower.

```bash
pip install "pratibmb[finetune-pytorch]"
pratibmb finetune train
```

- ~2 hours for 1,500 pairs
- No GPU required
- 8GB+ RAM recommended

---

## Privacy & Data

### Where is my data stored?

| Data | Location |
|------|----------|
| Messages database | `~/.pratibmb/corpus.db` |
| Configuration | `~/.pratibmb/config.json` |
| Models | `~/.pratibmb/models/` |
| Training data | `~/.pratibmb/finetune/data/` |
| LoRA adapter | `~/.pratibmb/finetune/adapter/` |
| Voice fingerprint | `~/.pratibmb/voice.json` |

### What never happens

- Your messages are **never uploaded** to any server
- No API calls are made to OpenAI, Google, Anthropic, or any other provider
- No crash reports, analytics, or telemetry are collected
- The app works **completely offline** after the initial model download
- Training data is blocked from git via `.gitignore`

### How to verify

1. Check your firewall — Pratibmb makes zero outbound connections during use
2. Read the source code — it's AGPLv3, every line is public
3. Run `lsof -i -P | grep pratibmb` — should only show `127.0.0.1:11435` (local server)

---

## Troubleshooting

### "waiting for the local server to start..."
The Python server hasn't started yet. Wait 10 seconds. If it persists:
- Check that Python 3.9+ is installed: `python3 --version`
- Check that pratibmb is installed: `pip install -e .` from the repo root
- Check port 11435 is free: `lsof -ti:11435`

### "embed model not found"
Place models in `~/.pratibmb/models/` or set environment variables:
```bash
export PRATIBMB_EMBED_MODEL=/path/to/nomic-embed-text-v1.5-q4_k_m.gguf
export PRATIBMB_CHAT_MODEL=/path/to/gemma-3-4b-it-q4_k_m.gguf
```

### "no importer could handle {path}"
The file format wasn't recognized. Make sure you're pointing at:
- WhatsApp: the `.txt` file (not a zip)
- Facebook/Instagram: the unzipped folder (not the zip)
- Gmail: the `.mbox` file or `Takeout/Mail/` folder
- Telegram: the export folder containing `result.json`
- Twitter: the unzipped archive containing `data/tweets.js`

### Short or terse replies
The fine-tuned model may have learned your short-reply tendency. Try:
1. Ask more specific questions ("what happened at work in 2018?" vs "hey")
2. Run profile extraction if you haven't: click the gear icon > Extract Profile
3. Consider re-training with more data from verbose conversations

### Model breaks character ("I'm an AI")
The base Gemma model sometimes leaks through. This is less frequent with:
1. Profile extraction (gives the model real biographical data)
2. Fine-tuning (overrides the base model's tendencies)
3. Asking questions that reference specific people or events from your life
