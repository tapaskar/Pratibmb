# Pratibmb for Linux

[![AUR](https://img.shields.io/badge/AUR-pratibmb--bin-1793d1?logo=archlinux&logoColor=white)](https://aur.archlinux.org/packages/pratibmb-bin)
[![Linux](https://img.shields.io/badge/Linux-x86__64-333?logo=linux&logoColor=white)](https://pratibmb.com)
[![License](https://img.shields.io/badge/license-AGPLv3-blue)](https://github.com/tapaskar/Pratibmb/blob/main/LICENSE)

> Chat with your 10-years-younger self. 100% local. No cloud. No telemetry.

## Install (Arch Linux)

```bash
yay -S pratibmb-bin
```

or

```bash
paru -S pratibmb-bin
```

## What is Pratibmb?

Pratibmb ingests your personal messaging history (WhatsApp, Facebook, Instagram, Gmail, iMessage, Telegram, Twitter/X, Discord), builds a private corpus on your machine, and lets you have a conversation with the person who sent those messages years ago. A local LLM learns your voice and responds as past-you. Everything runs offline.

## Requirements

- Linux x86_64 (tested on Ubuntu 22.04, Arch, Fedora)
- Python 3.10+
- ~4 GB RAM
- ~2.5 GB disk for AI models (downloaded on first launch)
- FUSE 2 (for AppImage)

## Fine-tuning (optional)

With an NVIDIA GPU (6 GB+ VRAM), Pratibmb can fine-tune the model on your texting style:

```bash
pip install "pratibmb[finetune-pytorch]"
```

Fine-tuning takes ~30 minutes for ~1500 message pairs. CPU-only works too (~2 hours).

## Direct download

If you're not on Arch:

| Format | Download |
|--------|----------|
| Debian/Ubuntu | [Pratibmb_0.2.0_amd64.deb](https://github.com/tapaskar/Pratibmb/releases/latest/download/Pratibmb_0.2.0_amd64.deb) |
| AppImage (universal) | [Pratibmb_0.2.0_amd64.AppImage](https://github.com/tapaskar/Pratibmb/releases/latest/download/Pratibmb_0.2.0_amd64.AppImage) |

### Install .deb

```bash
sudo dpkg -i Pratibmb_0.2.0_amd64.deb
```

### Run AppImage

```bash
chmod +x Pratibmb_0.2.0_amd64.AppImage
./Pratibmb_0.2.0_amd64.AppImage
```

## Uninstall

```bash
# AUR
yay -R pratibmb-bin

# Debian/Ubuntu
sudo apt remove pratibmb
```

## Links

- [Main repository](https://github.com/tapaskar/Pratibmb)
- [Website](https://pratibmb.com)
- [Documentation](https://github.com/tapaskar/Pratibmb/blob/main/docs/HELP.md)
- [Report an issue](https://github.com/tapaskar/Pratibmb/issues)

## License

Dual-licensed: [AGPLv3](https://github.com/tapaskar/Pratibmb/blob/main/LICENSE) for open use. [Commercial licenses](mailto:admin@sparkupcloud.com) available for proprietary products.
