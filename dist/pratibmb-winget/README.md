# Pratibmb for Windows

[![winget](https://img.shields.io/badge/winget-tapaskar.Pratibmb-0078d4?logo=windows&logoColor=white)](https://github.com/tapaskar/pratibmb-winget)
[![Windows](https://img.shields.io/badge/Windows-10%2F11-0078d4?logo=windows11&logoColor=white)](https://pratibmb.com)
[![License](https://img.shields.io/badge/license-AGPLv3-blue)](https://github.com/tapaskar/Pratibmb/blob/main/LICENSE)

> Chat with your 10-years-younger self. 100% local. No cloud. No telemetry.

## Install

```powershell
winget install tapaskar.Pratibmb
```

## What is Pratibmb?

Pratibmb ingests your personal messaging history (WhatsApp, Facebook, Instagram, Gmail, iMessage, Telegram, Twitter/X, Discord), builds a private corpus on your machine, and lets you have a conversation with the person who sent those messages years ago. A local LLM learns your voice and responds as past-you. Everything runs offline.

## Requirements

- Windows 10 or Windows 11 (64-bit)
- Python 3.10+
- ~4 GB RAM
- ~2.5 GB disk for AI models (downloaded on first launch)
- NVIDIA GPU with 6 GB+ VRAM (optional, for fine-tuning)

## Fine-tuning (optional)

With an NVIDIA GPU, Pratibmb can fine-tune the model on your texting style using CUDA:

```powershell
pip install "pratibmb[finetune-pytorch]"
```

Fine-tuning takes ~30 minutes for ~1500 message pairs.

## Direct download

If you prefer not to use winget:

| Format | Download |
|--------|----------|
| Installer (.exe) | [Pratibmb_0.0.1_x64-setup.exe](https://github.com/tapaskar/Pratibmb/releases/latest/download/Pratibmb_0.0.1_x64-setup.exe) |
| MSI | [Pratibmb_0.0.1_x64_en-US.msi](https://github.com/tapaskar/Pratibmb/releases/latest/download/Pratibmb_0.0.1_x64_en-US.msi) |

## Uninstall

```powershell
winget uninstall tapaskar.Pratibmb
```

Or via Settings > Apps > Pratibmb > Uninstall.

## Links

- [Main repository](https://github.com/tapaskar/Pratibmb)
- [Website](https://pratibmb.com)
- [Documentation](https://github.com/tapaskar/Pratibmb/blob/main/docs/HELP.md)
- [Report an issue](https://github.com/tapaskar/Pratibmb/issues)

## License

Dual-licensed: [AGPLv3](https://github.com/tapaskar/Pratibmb/blob/main/LICENSE) for open use. [Commercial licenses](mailto:tapas.eric@gmail.com) available for proprietary products.
