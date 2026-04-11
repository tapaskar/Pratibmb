"""
Convert an MLX LoRA adapter to GGUF format for llama-cpp-python.

MLX-LM saves adapters as .safetensors files. To use them with
llama-cpp-python, we need to convert to a GGUF LoRA adapter file.

Conversion strategies (tried in order):
  1. llama.cpp's convert_lora_to_gguf.py script
  2. Manual conversion using safetensors + struct packing
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


def _find_llama_cpp_converter() -> str | None:
    """Try to find the llama.cpp LoRA-to-GGUF converter script."""
    # Check env var
    script = os.environ.get("LLAMA_CPP_CONVERT_LORA", "")
    if script and Path(script).exists():
        return script

    # Check common locations
    candidates = [
        Path.home() / "llama.cpp" / "convert_lora_to_gguf.py",
        Path("/usr/local/share/llama.cpp/convert_lora_to_gguf.py"),
        Path.home() / "src" / "llama.cpp" / "convert_lora_to_gguf.py",
    ]

    # Also check LLAMA_CPP_DIR
    llama_dir = os.environ.get("LLAMA_CPP_DIR", "")
    if llama_dir:
        candidates.insert(0, Path(llama_dir) / "convert_lora_to_gguf.py")

    for c in candidates:
        if c.exists():
            return str(c)

    # Try finding it on PATH via which
    result = shutil.which("convert_lora_to_gguf.py")
    if result:
        return result

    return None


def convert_adapter(
    adapter_dir: Path | str,
    output_path: Path | str | None = None,
    base_model: str = "google/gemma-3-4b-it",
) -> dict[str, Any]:
    """Convert an MLX LoRA adapter to GGUF format.

    Args:
        adapter_dir: Directory containing the MLX adapter (.safetensors).
        output_path: Where to save the GGUF file. Defaults to
                     ~/.pratibmb/models/adapter.gguf.
        base_model: HuggingFace model name for architecture reference.

    Returns:
        Dict with status, output_path, and any messages.
    """
    adapter_dir = Path(adapter_dir)
    if not adapter_dir.exists():
        return {
            "status": "error",
            "error": f"Adapter directory not found: {adapter_dir}",
        }

    # Check for adapter files
    safetensors = list(adapter_dir.glob("*.safetensors"))
    npz_files = list(adapter_dir.glob("*.npz"))
    if not safetensors and not npz_files:
        return {
            "status": "error",
            "error": (
                f"No adapter weights found in {adapter_dir}. "
                "Expected .safetensors or .npz files."
            ),
        }

    # Default output path
    if output_path is None:
        env_dir = os.environ.get("PRATIBMB_DATA_DIR", "")
        default_dir = Path(env_dir) if env_dir else (Path.home() / ".pratibmb")
        output_path = default_dir / "models" / "adapter.gguf"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Strategy 1: llama.cpp converter
    converter = _find_llama_cpp_converter()
    if converter:
        return _convert_via_llama_cpp(
            converter, adapter_dir, output_path, base_model
        )

    # Strategy 2: Manual conversion
    return _convert_manual(adapter_dir, output_path, base_model)


def _convert_via_llama_cpp(
    converter: str,
    adapter_dir: Path,
    output_path: Path,
    base_model: str,
) -> dict[str, Any]:
    """Convert using llama.cpp's convert_lora_to_gguf.py."""
    cmd = [
        sys.executable,
        converter,
        "--base", base_model,
        "--outfile", str(output_path),
        str(adapter_dir),
    ]

    print(f"[convert] Running: {' '.join(cmd)}", flush=True)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
        )
        if result.returncode != 0:
            return {
                "status": "error",
                "error": f"Conversion failed:\n{result.stderr}",
                "stdout": result.stdout,
            }
        return {
            "status": "ok",
            "output_path": str(output_path),
            "method": "llama_cpp",
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "Conversion timed out."}
    except FileNotFoundError:
        return {
            "status": "error",
            "error": f"Python not found: {sys.executable}",
        }


def _convert_manual(
    adapter_dir: Path,
    output_path: Path,
    base_model: str,
) -> dict[str, Any]:
    """Attempt manual conversion or provide instructions."""
    instructions = f"""
Automatic GGUF conversion requires llama.cpp's converter script.

To convert manually:

1. Clone llama.cpp:
   git clone https://github.com/ggerganov/llama.cpp ~/llama.cpp

2. Run the converter:
   python ~/llama.cpp/convert_lora_to_gguf.py \\
     --base {base_model} \\
     --outfile {output_path} \\
     {adapter_dir}

3. The adapter will be saved to:
   {output_path}

Alternatively, set the LLAMA_CPP_DIR or LLAMA_CPP_CONVERT_LORA
environment variable to point to your llama.cpp installation.
""".strip()

    return {
        "status": "manual",
        "instructions": instructions,
        "adapter_dir": str(adapter_dir),
        "output_path": str(output_path),
    }
