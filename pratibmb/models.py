"""
Auto-download and resolve model paths.

On first launch, downloads pre-quantized GGUF files from HuggingFace Hub.
After that, everything runs offline — no network calls.

Models:
  Chat:  bartowski/google_gemma-3-4b-it-GGUF → Q4_K_M (2.49 GB)
  Embed: nomic-ai/nomic-embed-text-v1.5-GGUF → Q4_K_M (84 MB)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ── Model registry ──────────────────────────────────────────────────────
MODELS = {
    "chat": {
        "repo_id": "bartowski/google_gemma-3-4b-it-GGUF",
        "filename": "google_gemma-3-4b-it-Q4_K_M.gguf",
        "local_name": "gemma-3-4b-it-q4_k_m.gguf",
        "size_gb": 2.49,
        "description": "Gemma-3-4B-Instruct (chat model)",
    },
    "embed": {
        "repo_id": "nomic-ai/nomic-embed-text-v1.5-GGUF",
        "filename": "nomic-embed-text-v1.5.Q4_K_M.gguf",
        "local_name": "nomic-embed-text-v1.5-q4_k_m.gguf",
        "size_gb": 0.084,
        "description": "Nomic Embed Text v1.5 (embedding model)",
    },
}

# Fine-tuned model name (produced by finetune pipeline)
FINETUNED_NAME = "pratibmb-gemma-3-4b-finetuned-q4_k_m.gguf"

# ── Paths ───────────────────────────────────────────────────────────────
def models_dir() -> Path:
    """Return the models directory, creating it if needed."""
    d = Path.home() / ".pratibmb" / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _search_dirs() -> list[Path]:
    """Directories to search for models, in priority order."""
    return [
        models_dir(),
        Path.home() / "models",
        Path.cwd() / "models",
    ]


# ── Resolution ──────────────────────────────────────────────────────────
def resolve(
    kind: str,
    *,
    env_key: str | None = None,
    auto_download: bool = True,
) -> str:
    """Resolve a model path. Downloads from HuggingFace if not found locally.

    Args:
        kind: "chat" or "embed"
        env_key: Optional env var override (e.g. PRATIBMB_CHAT_MODEL)
        auto_download: If True, download the model when not found locally.

    Returns:
        Absolute path to the GGUF file, or "" if not found and download disabled.
    """
    info = MODELS.get(kind)
    if info is None:
        raise ValueError(f"Unknown model kind: {kind!r}. Expected 'chat' or 'embed'.")

    # 1. Check env var override
    if env_key:
        v = os.environ.get(env_key, "")
        if v and Path(v).exists():
            return v

    # 2. For chat: prefer fine-tuned model over base
    if kind == "chat":
        for d in _search_dirs():
            p = d / FINETUNED_NAME
            if p.exists():
                print(f"[models] using fine-tuned model: {p}", flush=True)
                return str(p)

    # 3. Check local copies
    for d in _search_dirs():
        p = d / info["local_name"]
        if p.exists():
            return str(p)

    # 4. Auto-download from HuggingFace
    if auto_download:
        return _download(kind)

    return ""


def resolve_chat(auto_download: bool = True) -> str:
    """Resolve the chat model path."""
    return resolve("chat", env_key="PRATIBMB_CHAT_MODEL", auto_download=auto_download)


def resolve_embed(auto_download: bool = True) -> str:
    """Resolve the embedding model path."""
    return resolve("embed", env_key="PRATIBMB_EMBED_MODEL", auto_download=auto_download)


# ── Download ────────────────────────────────────────────────────────────
def _download(kind: str) -> str:
    """Download a model from HuggingFace Hub.

    Uses huggingface_hub if available, falls back to a manual HTTPS download.
    Returns the local path to the downloaded file.
    """
    info = MODELS[kind]
    dest = models_dir() / info["local_name"]

    print(
        f"[models] downloading {info['description']} "
        f"({info['size_gb']:.1f} GB) ...",
        flush=True,
    )
    print(
        f"[models] source: huggingface.co/{info['repo_id']}",
        flush=True,
    )

    try:
        return _download_via_hub(info, dest)
    except ImportError:
        print("[models] huggingface_hub not installed, using direct download", flush=True)
        return _download_direct(info, dest)


def _download_via_hub(info: dict, dest: Path) -> str:
    """Download using the huggingface_hub library (preferred — shows progress)."""
    from huggingface_hub import hf_hub_download

    # Download to HF cache, then symlink/copy to our models dir
    cached = hf_hub_download(
        repo_id=info["repo_id"],
        filename=info["filename"],
        local_dir=str(dest.parent),
        local_dir_use_symlinks=False,
    )

    # hf_hub_download with local_dir puts the file right there
    # but the filename may differ from our local_name
    downloaded = dest.parent / info["filename"]
    if downloaded.exists() and not dest.exists():
        downloaded.rename(dest)
    elif not dest.exists():
        # If it landed somewhere else, copy it
        import shutil
        shutil.copy2(cached, dest)

    print(f"[models] saved to {dest}", flush=True)
    return str(dest)


def _download_direct(info: dict, dest: Path) -> str:
    """Fallback: download via urllib (no extra deps, basic progress)."""
    import urllib.request

    url = (
        f"https://huggingface.co/{info['repo_id']}"
        f"/resolve/main/{info['filename']}"
    )

    # Download with progress
    tmp = dest.with_suffix(".tmp")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "pratibmb/0.1"})
        with urllib.request.urlopen(req) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            last_pct = -1

            with open(tmp, "wb") as f:
                while True:
                    chunk = resp.read(1024 * 1024)  # 1 MB chunks
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)

                    if total > 0:
                        pct = int(downloaded * 100 / total)
                        if pct != last_pct and pct % 5 == 0:
                            mb = downloaded / (1024 * 1024)
                            total_mb = total / (1024 * 1024)
                            print(
                                f"[models] {pct}% ({mb:.0f}/{total_mb:.0f} MB)",
                                flush=True,
                            )
                            last_pct = pct

        tmp.rename(dest)
        print(f"[models] saved to {dest}", flush=True)
        return str(dest)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


# ── Status ──────────────────────────────────────────────────────────────
def status() -> dict:
    """Return download/availability status for all models."""
    result = {}
    for kind, info in MODELS.items():
        path = resolve(kind, auto_download=False)
        result[kind] = {
            "name": info["description"],
            "size_gb": info["size_gb"],
            "available": bool(path),
            "path": path,
            "finetuned": False,
        }
        # Check for fine-tuned variant
        if kind == "chat":
            for d in _search_dirs():
                ft = d / FINETUNED_NAME
                if ft.exists():
                    result[kind]["finetuned"] = True
                    result[kind]["finetuned_path"] = str(ft)
                    break
    return result
