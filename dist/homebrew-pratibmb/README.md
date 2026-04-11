# Pratibmb for macOS

[![Homebrew](https://img.shields.io/badge/homebrew-tap-orange?logo=homebrew&logoColor=white)](https://github.com/tapaskar/homebrew-pratibmb)
[![macOS](https://img.shields.io/badge/macOS-12%2B-black?logo=apple&logoColor=white)](https://pratibmb.com)
[![License](https://img.shields.io/badge/license-AGPLv3-blue)](https://github.com/tapaskar/Pratibmb/blob/main/LICENSE)

> Chat with your 10-years-younger self. 100% local. No cloud. No telemetry.

## Install

```bash
brew tap tapaskar/pratibmb
brew install --cask pratibmb
```

That's it. Pratibmb appears in your Applications folder.

## What is Pratibmb?

Pratibmb ingests your personal messaging history (WhatsApp, Facebook, Instagram, Gmail, iMessage, Telegram, Twitter/X, Discord), builds a private corpus on your machine, and lets you have a conversation with the person who sent those messages years ago. A local LLM learns your voice and responds as past-you. Everything runs offline.

## Requirements

- macOS 12 (Monterey) or later
- Apple Silicon (M1/M2/M3/M4) or Intel Mac
- Python 3.10+
- ~4 GB RAM
- ~2.5 GB disk for AI models (downloaded on first launch)

## Fine-tuning (optional)

On Apple Silicon, Pratibmb can fine-tune the model on your texting style using Metal acceleration via MLX:

```bash
pip install mlx-lm
```

Fine-tuning takes ~20 minutes for ~1500 message pairs.

## Direct download

If you prefer not to use Homebrew:

| Chip | Download |
|------|----------|
| Apple Silicon (M1+) | [Pratibmb_0.0.1_aarch64.dmg](https://github.com/tapaskar/Pratibmb/releases/latest/download/Pratibmb_0.0.1_aarch64.dmg) |
| Intel | [Pratibmb_0.0.1_x64.dmg](https://github.com/tapaskar/Pratibmb/releases/latest/download/Pratibmb_0.0.1_x64.dmg) |

## Uninstall

```bash
brew uninstall pratibmb
brew untap tapaskar/pratibmb
```

## Links

- [Main repository](https://github.com/tapaskar/Pratibmb)
- [Website](https://pratibmb.com)
- [Documentation](https://github.com/tapaskar/Pratibmb/blob/main/docs/HELP.md)
- [Report an issue](https://github.com/tapaskar/Pratibmb/issues)

## License

Dual-licensed: [AGPLv3](https://github.com/tapaskar/Pratibmb/blob/main/LICENSE) for open use. [Commercial licenses](mailto:tapas.eric@gmail.com) available for proprietary products.
