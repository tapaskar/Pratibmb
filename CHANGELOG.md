# Changelog

All notable changes to Pratibmb are documented here.

## [0.5.0] — 2026-04-13

### Added
- Windows desktop app support with NSIS installer (.exe) and MSI
- Auto-install Python package on first launch if missing
- RAM check in install scripts (warns if <8GB)
- Retry logic for llama-cpp-python wheel install on Windows
- Help modal with visual navigation paths for all 8 platforms
- Troubleshooting FAQ with expandable answers
- Diagnostics section with Report Issue, Copy Logs buttons
- 14 app screenshots for documentation

### Fixed
- Python console window no longer overlaps the app on Windows (CREATE_NO_WINDOW)
- SQLite threading crash with concurrent requests (check_same_thread + Lock)
- Server now handles concurrent requests via ThreadedHTTPServer

### Changed
- Minimum RAM recommendation increased from 4GB to 8GB
- NSIS installer supports both per-user and per-machine install

## [0.4.0] — 2026-04-10

### Added
- Relaxed Python requirement to 3.9+ (was 3.10+)
- Distribution repos for Homebrew, AUR, and winget

### Fixed
- Logging initialization order in server startup
- `use tauri::Manager` import for app.manage() in setup hook

## [0.3.0] — 2026-04-08

### Added
- Data reset and deletion features (Reset Fine-Tuning, Reset Profile, Delete All)
- Diagnostic logging with structured log files
- One-click bug reporting (copies logs, opens GitHub issue)
- Privacy-safe log export (timestamps and operations only, no message content)

## [0.2.0] — 2026-04-05

### Added
- LoRA fine-tuning pipeline (MLX for Apple Silicon, PyTorch/QLoRA for NVIDIA)
- Profile extraction from messages (relationships, life events, interests, communication style)
- Training pair extraction for fine-tuning
- Adapter conversion to GGUF format
- Year slider for time-travel conversations
- Thread context expansion in RAG retrieval

## [0.1.0] — 2026-04-01

### Added
- Initial release
- Chat import from 8 platforms (WhatsApp, Facebook, Instagram, Gmail, iMessage, Telegram, Twitter/X, Discord)
- Local embedding via Nomic Embed Text v1.5 (84MB GGUF)
- RAG-based chat with Gemma-3-4B-Instruct (2.3GB GGUF)
- Tauri 2 desktop app (macOS, Linux)
- Onboarding wizard with guided setup
- 100% local processing, no cloud, no telemetry
