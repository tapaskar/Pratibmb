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
import time
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

# Fine-tuned model names (produced by finetune pipeline)
FINETUNED_NAME = "pratibmb-gemma-3-4b-finetuned-q4_k_m.gguf"
ADAPTER_NAME = "adapter.gguf"  # LoRA adapter (used alongside base model)

# Download settings
MAX_RETRIES = 3
RETRY_DELAY_SECS = 5

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

    # 4. Check for partial downloads (interrupted)
    partial = models_dir() / (info["local_name"] + ".tmp")
    if partial.exists():
        size_mb = partial.stat().st_size / (1024 * 1024)
        print(
            f"[models] found partial download ({size_mb:.0f} MB), will resume",
            flush=True,
        )

    # 5. Auto-download from HuggingFace
    if auto_download:
        return _download_with_retry(kind)

    return ""


def resolve_chat(auto_download: bool = True) -> str:
    """Resolve the chat model path."""
    return resolve("chat", env_key="PRATIBMB_CHAT_MODEL", auto_download=auto_download)


def resolve_embed(auto_download: bool = True) -> str:
    """Resolve the embedding model path."""
    return resolve("embed", env_key="PRATIBMB_EMBED_MODEL", auto_download=auto_download)


# ── Download with retry ─────────────────────────────────────────────────
def _download_with_retry(kind: str) -> str:
    """Download a model with retry logic.

    Tries huggingface_hub first (supports resume natively), then falls back
    to direct urllib download with manual resume support.
    """
    info = MODELS[kind]
    dest = models_dir() / info["local_name"]

    print(
        f"[models] downloading {info['description']} "
        f"({info['size_gb']:.2f} GB) ...",
        flush=True,
    )
    print(
        f"[models] source: huggingface.co/{info['repo_id']}",
        flush=True,
    )

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            try:
                return _download_via_hub(info, dest)
            except ImportError:
                print(
                    "[models] huggingface_hub not installed, using direct download",
                    flush=True,
                )
                return _download_direct(info, dest)
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES:
                print(
                    f"[models] download failed (attempt {attempt}/{MAX_RETRIES}): {e}",
                    flush=True,
                )
                print(
                    f"[models] retrying in {RETRY_DELAY_SECS} seconds...",
                    flush=True,
                )
                time.sleep(RETRY_DELAY_SECS)
            else:
                print(
                    f"[models] download failed after {MAX_RETRIES} attempts: {e}",
                    flush=True,
                )

    # All retries exhausted
    raise RuntimeError(
        f"Failed to download {info['description']} after {MAX_RETRIES} attempts. "
        f"Last error: {last_error}\n"
        f"You can manually download from:\n"
        f"  https://huggingface.co/{info['repo_id']}\n"
        f"and place {info['filename']} at:\n"
        f"  {dest}"
    )


def _download_via_hub(info: dict, dest: Path) -> str:
    """Download using the huggingface_hub library (preferred — supports resume)."""
    from huggingface_hub import hf_hub_download

    # hf_hub_download handles resume and caching natively
    cached = hf_hub_download(
        repo_id=info["repo_id"],
        filename=info["filename"],
        local_dir=str(dest.parent),
        local_dir_use_symlinks=False,
    )

    # hf_hub_download with local_dir puts the file in dest.parent
    # but the filename may differ from our local_name
    downloaded = dest.parent / info["filename"]
    if downloaded.exists() and not dest.exists():
        downloaded.rename(dest)
    elif not dest.exists():
        import shutil
        shutil.copy2(cached, dest)

    print(f"[models] saved to {dest}", flush=True)
    return str(dest)


def _download_direct(info: dict, dest: Path) -> str:
    """Fallback: download via urllib with resume support."""
    import urllib.request

    url = (
        f"https://huggingface.co/{info['repo_id']}"
        f"/resolve/main/{info['filename']}"
    )

    tmp = dest.with_suffix(".tmp")
    existing_size = tmp.stat().st_size if tmp.exists() else 0

    try:
        headers = {"User-Agent": "pratibmb/0.1"}

        # Resume from where we left off
        if existing_size > 0:
            headers["Range"] = f"bytes={existing_size}-"
            print(
                f"[models] resuming download from {existing_size / (1024*1024):.0f} MB",
                flush=True,
            )

        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            # Handle resume response (206 Partial Content)
            if resp.status == 206:
                content_range = resp.headers.get("Content-Range", "")
                # Content-Range: bytes 1234-5678/9999
                total = int(content_range.split("/")[-1]) if "/" in content_range else 0
                downloaded = existing_size
                mode = "ab"  # append
            else:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                existing_size = 0
                mode = "wb"  # overwrite (server doesn't support resume)

            last_pct = -1

            with open(tmp, mode) as f:
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
        # DON'T delete tmp — allows resume on next attempt
        if tmp.exists():
            size_mb = tmp.stat().st_size / (1024 * 1024)
            print(
                f"[models] download interrupted at {size_mb:.0f} MB (will resume)",
                flush=True,
            )
        raise


# ── Status ──────────────────────────────────────────────────────────────
def status() -> dict:
    """Return download/availability status for all models."""
    result = {}
    for kind, info in MODELS.items():
        path = resolve(kind, auto_download=False)
        entry: dict = {
            "name": info["description"],
            "size_gb": info["size_gb"],
            "available": bool(path),
            "path": path,
            "finetuned": False,
        }

        # Check for partial download
        partial = models_dir() / (info["local_name"] + ".tmp")
        if partial.exists() and not entry["available"]:
            entry["partial_mb"] = round(
                partial.stat().st_size / (1024 * 1024), 1
            )

        # Check for fine-tuned variant
        if kind == "chat":
            for d in _search_dirs():
                ft = d / FINETUNED_NAME
                if ft.exists():
                    entry["finetuned"] = True
                    entry["finetuned_path"] = str(ft)
                    break
            # Check for LoRA adapter
            for d in _search_dirs():
                adp = d / ADAPTER_NAME
                if adp.exists():
                    entry["has_adapter"] = True
                    entry["adapter_path"] = str(adp)
                    break

        result[kind] = entry
    return result
