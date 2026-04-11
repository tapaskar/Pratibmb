"""
Convert an MLX LoRA adapter to GGUF format for llama-cpp-python.

MLX-LM saves adapters as .safetensors files. To use them with
llama-cpp-python, we need to produce a full GGUF model file.

Conversion strategies (tried in order):
  1. MLX-LM fuse → HF safetensors, then convert_hf_to_gguf.py
  2. llama.cpp's convert_lora_to_gguf.py (if available locally)
  3. Manual instructions fallback

The converter script is auto-downloaded from llama.cpp's GitHub
if not found locally — no need to clone the entire repo.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


# ── Default output paths ────────────────────────────────────────────────

def _pratibmb_dir() -> Path:
    env_dir = os.environ.get("PRATIBMB_DATA_DIR", "")
    return Path(env_dir) if env_dir else (Path.home() / ".pratibmb")


def _models_dir() -> Path:
    d = _pratibmb_dir() / "models"
    d.mkdir(parents=True, exist_ok=True)
    return d


FINETUNED_GGUF_NAME = "pratibmb-gemma-3-4b-finetuned-q4_k_m.gguf"

# llama.cpp converter scripts (auto-downloaded if needed)
CONVERTER_DIR = _pratibmb_dir() / "tools" / "llama-cpp"
HF_TO_GGUF_URL = (
    "https://raw.githubusercontent.com/ggerganov/llama.cpp/master/"
    "convert_hf_to_gguf.py"
)
LORA_TO_GGUF_URL = (
    "https://raw.githubusercontent.com/ggerganov/llama.cpp/master/"
    "convert_lora_to_gguf.py"
)


# ── Public API ──────────────────────────────────────────────────────────

def convert_adapter(
    adapter_dir: Path | str,
    output_path: Path | str | None = None,
    base_model: str = "mlx-community/gemma-3-4b-it-8bit",
) -> dict[str, Any]:
    """Convert an MLX LoRA adapter to GGUF format.

    Tries strategies in order until one succeeds:
      1. mlx-lm fuse → convert_hf_to_gguf.py (auto-downloaded)
      2. llama.cpp convert_lora_to_gguf.py (local or auto-downloaded)
      3. Fallback to manual instructions

    Args:
        adapter_dir: Directory containing the MLX adapter (.safetensors).
        output_path: Where to save the GGUF file. Defaults to
                     ~/.pratibmb/models/pratibmb-gemma-3-4b-finetuned-q4_k_m.gguf
        base_model: Model to fuse with (HuggingFace repo or local path).

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

    # Default output path — produce a full merged GGUF
    if output_path is None:
        output_path = _models_dir() / FINETUNED_GGUF_NAME
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    errors = []

    # Strategy 1: Direct LoRA-to-GGUF (produces adapter.gguf ~10 MB)
    # This is the lightest approach — produces a LoRA adapter file that
    # llama-cpp-python loads on top of the base GGUF model.
    adapter_gguf = output_path.parent / "adapter.gguf"
    result = _convert_lora_to_gguf(adapter_dir, adapter_gguf, base_model)
    if result["status"] == "ok":
        return result
    errors.append(("lora-gguf", result.get("error", "unknown")))

    # Strategy 2: MLX-LM fuse → convert to full GGUF
    # Merges adapter into base model, producing a standalone GGUF.
    result = _fuse_then_convert(adapter_dir, output_path, base_model)
    if result["status"] == "ok":
        return result
    errors.append(("mlx-fuse", result.get("error", "unknown")))

    # Strategy 3: Manual instructions
    return _manual_instructions(
        adapter_dir, output_path, base_model, errors
    )


# ── Strategy 1: MLX fuse → HF model → GGUF ────────────────────────────

def _fuse_then_convert(
    adapter_dir: Path,
    output_path: Path,
    base_model: str,
) -> dict[str, Any]:
    """Fuse adapter into base model, then convert to GGUF.

    Step 1: mlx_lm fuse (creates full HF safetensors model)
    Step 2: convert_hf_to_gguf.py (converts to GGUF format)
    """
    # Check mlx-lm is available
    try:
        import mlx_lm  # noqa: F401
    except ImportError:
        return {
            "status": "error",
            "error": "mlx-lm not installed (pip install mlx-lm)",
        }

    fused_dir = adapter_dir.parent / "fused_model"

    # Step 1: Fuse adapter weights into base model
    print("[convert] Step 1/2: Fusing adapter into base model...", flush=True)
    fuse_result = _mlx_fuse(adapter_dir, fused_dir, base_model)
    if fuse_result["status"] != "ok":
        return fuse_result

    # Step 2: Convert fused model to GGUF
    print("[convert] Step 2/2: Converting to GGUF...", flush=True)
    converter = _get_converter("convert_hf_to_gguf.py", HF_TO_GGUF_URL)
    if converter is None:
        _safe_cleanup(fused_dir)
        return {
            "status": "error",
            "error": (
                "Could not get convert_hf_to_gguf.py. "
                "Network unavailable and script not cached."
            ),
        }

    # Ensure required packages are installed
    _ensure_gguf_package()
    if not _ensure_torch():
        _safe_cleanup(fused_dir)
        return {
            "status": "error",
            "error": (
                "torch is required for GGUF conversion but could not be installed. "
                "Run: pip install torch"
            ),
        }

    convert_result = _run_converter(
        converter,
        ["--outtype", "f16", "--outfile", str(output_path), str(fused_dir)],
    )

    # Clean up fused model (can be several GB)
    _safe_cleanup(fused_dir)

    if convert_result["status"] == "ok":
        if output_path.exists():
            size_mb = output_path.stat().st_size / (1024 * 1024)
            print(
                f"[convert] Done! {output_path.name} ({size_mb:.0f} MB)",
                flush=True,
            )
            convert_result["output_path"] = str(output_path)
            convert_result["size_mb"] = round(size_mb, 1)
            convert_result["method"] = "mlx_fuse+hf_to_gguf"

    return convert_result


def _mlx_fuse(
    adapter_dir: Path,
    fused_dir: Path,
    base_model: str,
) -> dict[str, Any]:
    """Run mlx_lm fuse (NO --export-gguf, just merge weights)."""
    cmd = [
        sys.executable, "-m", "mlx_lm", "fuse",
        "--model", base_model,
        "--adapter-path", str(adapter_dir),
        "--save-path", str(fused_dir),
    ]

    print(f"[convert:mlx] Base: {base_model}", flush=True)
    print(f"[convert:mlx] Adapter: {adapter_dir}", flush=True)

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=1800,
        )
        if result.returncode != 0:
            return {
                "status": "error",
                "error": f"MLX fuse failed:\n{result.stderr[-1500:]}",
            }

        # Verify fused model exists
        if not fused_dir.exists() or not list(fused_dir.glob("*.safetensors")):
            return {
                "status": "error",
                "error": f"Fuse completed but no model found at {fused_dir}",
            }

        print(f"[convert:mlx] Fused model saved to {fused_dir}", flush=True)
        return {"status": "ok"}

    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "MLX fuse timed out after 30 min."}
    except FileNotFoundError:
        return {"status": "error", "error": f"Python not found: {sys.executable}"}


# ── Strategy 2: Direct LoRA → GGUF ─────────────────────────────────────

def _convert_lora_to_gguf(
    adapter_dir: Path,
    output_path: Path,
    base_model: str,
) -> dict[str, Any]:
    """Convert LoRA adapter directly to GGUF (adapter-only file ~10 MB).

    Uses the HuggingFace base model for architecture info (not MLX model).
    The base model config is downloaded but weights are not needed.
    """
    converter = _get_converter("convert_lora_to_gguf.py", LORA_TO_GGUF_URL)
    if converter is None:
        return {
            "status": "error",
            "error": "convert_lora_to_gguf.py not available",
        }

    _ensure_gguf_package()
    if not _ensure_torch():
        return {
            "status": "error",
            "error": "torch required for LoRA conversion",
        }

    # Use HuggingFace base model (not MLX) for architecture info
    hf_base = base_model
    if "mlx-community" in hf_base:
        # Map MLX model name back to HuggingFace original
        hf_base = hf_base.replace("mlx-community/", "").replace("-8bit", "")
        # e.g., "mlx-community/gemma-3-4b-it-8bit" → "google/gemma-3-4b-it"
        hf_base = f"google/{hf_base}"

    print(f"[convert:lora] Adapter: {adapter_dir}", flush=True)
    print(f"[convert:lora] Base model (for arch): {hf_base}", flush=True)
    print(f"[convert:lora] Output: {output_path}", flush=True)

    # Create a PEFT-compatible staging directory
    # MLX saves as "adapters.safetensors" but PEFT expects "adapter_model.safetensors"
    staging_dir = _prepare_peft_compatible_dir(adapter_dir, hf_base)
    convert_dir = staging_dir if staging_dir else adapter_dir

    result = _run_converter(
        converter,
        ["--base", hf_base, "--outfile", str(output_path), str(convert_dir)],
    )

    # Clean up staging dir if we created one
    if staging_dir and staging_dir != adapter_dir:
        _safe_cleanup(staging_dir)

    if result["status"] == "ok":
        if output_path.exists():
            size_mb = output_path.stat().st_size / (1024 * 1024)
            result["output_path"] = str(output_path)
            result["size_mb"] = round(size_mb, 1)
            result["method"] = "lora_to_gguf"
            print(
                f"[convert:lora] Done! {output_path.name} ({size_mb:.1f} MB)",
                flush=True,
            )
    return result


# ── MLX → PEFT compatibility ────────────────────────────────────────────

def _prepare_peft_compatible_dir(
    adapter_dir: Path,
    base_model: str,
) -> Path | None:
    """Create a PEFT-compatible adapter directory from MLX adapter files.

    MLX-LM saves adapters as `adapters.safetensors` with MLX-style weight
    names (e.g., `layers.0.self_attn.q_proj.lora_a`). PEFT/llama.cpp
    expects `adapter_model.safetensors` with PEFT-style names
    (e.g., `base_model.model.model.layers.0.self_attn.q_proj.lora_A.weight`).

    Returns path to the staging directory, or None if not needed.
    """
    mlx_weights = adapter_dir / "adapters.safetensors"
    peft_weights = adapter_dir / "adapter_model.safetensors"

    # If already PEFT format, no conversion needed
    if peft_weights.exists():
        return None

    if not mlx_weights.exists():
        return None

    print("[convert:lora] Converting MLX adapter names to PEFT format...", flush=True)

    staging = adapter_dir.parent / "adapter_peft_staging"
    staging.mkdir(parents=True, exist_ok=True)

    try:
        from safetensors.torch import load_file, save_file
    except ImportError:
        try:
            from safetensors import safe_open
            import torch

            # Load MLX safetensors
            tensors = {}
            with safe_open(str(mlx_weights), framework="pt") as f:
                for key in f.keys():
                    tensors[key] = f.get_tensor(key)
        except Exception as e:
            print(f"[convert:lora] Could not load safetensors: {e}", flush=True)
            return None
    else:
        tensors = load_file(str(mlx_weights))

    # Map MLX weight names to PEFT format
    peft_tensors = {}
    for key, tensor in tensors.items():
        peft_key = _mlx_to_peft_key(key)
        peft_tensors[peft_key] = tensor

    # Save in PEFT format
    try:
        save_file(peft_tensors, str(staging / "adapter_model.safetensors"))
    except NameError:
        # save_file not available, try manual save
        import torch
        torch.save(peft_tensors, str(staging / "adapter_model.bin"))

    # Create PEFT adapter_config.json
    adapter_config = _make_peft_config(adapter_dir, base_model)
    (staging / "adapter_config.json").write_text(json.dumps(adapter_config, indent=2))

    print(f"[convert:lora] Staged {len(peft_tensors)} tensors at {staging}", flush=True)
    return staging


def _mlx_to_peft_key(key: str) -> str:
    """Convert MLX LoRA weight name to PEFT format.

    MLX:  layers.0.self_attn.q_proj.lora_a
    PEFT: base_model.model.model.layers.0.self_attn.q_proj.lora_A.weight
    """
    peft_key = key
    # Add PEFT prefix
    if not peft_key.startswith("base_model."):
        peft_key = f"base_model.model.model.{peft_key}"
    # Fix casing: lora_a → lora_A, lora_b → lora_B
    peft_key = peft_key.replace(".lora_a", ".lora_A.weight")
    peft_key = peft_key.replace(".lora_b", ".lora_B.weight")
    return peft_key


def _make_peft_config(adapter_dir: Path, base_model: str) -> dict:
    """Create a PEFT-compatible adapter_config.json from MLX config."""
    config = {
        "auto_mapping": None,
        "base_model_name_or_path": base_model,
        "bias": "none",
        "fan_in_fan_out": False,
        "inference_mode": True,
        "init_lora_weights": True,
        "lora_alpha": 16,
        "lora_dropout": 0.05,
        "modules_to_save": None,
        "peft_type": "LORA",
        "r": 8,
        "revision": None,
        "target_modules": ["q_proj", "v_proj", "k_proj", "o_proj"],
        "task_type": "CAUSAL_LM",
    }

    # Read actual values from MLX config if available
    mlx_config_path = adapter_dir / "adapter_config.json"
    if mlx_config_path.exists():
        mlx_cfg = json.loads(mlx_config_path.read_text())
        lora_params = mlx_cfg.get("lora_parameters", {})
        if "rank" in lora_params:
            config["r"] = lora_params["rank"]
        if "scale" in lora_params:
            config["lora_alpha"] = int(lora_params["scale"])
        if "dropout" in lora_params:
            config["lora_dropout"] = lora_params["dropout"]

    return config


# ── Converter script management ────────────────────────────────────────

def _find_local_converter(script_name: str) -> str | None:
    """Try to find a converter script in local installations."""
    # Check env vars
    for env_key in ["LLAMA_CPP_CONVERT_LORA", "LLAMA_CPP_DIR"]:
        val = os.environ.get(env_key, "")
        if val:
            if env_key == "LLAMA_CPP_DIR":
                val = str(Path(val) / script_name)
            if Path(val).exists():
                return val

    # Common local paths
    candidates = [
        Path.home() / "llama.cpp" / script_name,
        Path("/usr/local/share/llama.cpp") / script_name,
        Path.home() / "src" / "llama.cpp" / script_name,
    ]
    for c in candidates:
        if c.exists():
            return str(c)

    # Check PATH
    result = shutil.which(script_name)
    if result:
        return result

    # Check our cached tools dir
    cached = CONVERTER_DIR / script_name
    if cached.exists():
        return str(cached)

    return None


def _get_converter(script_name: str, url: str) -> str | None:
    """Get a converter script — prefer our cached latest, then download.

    We prefer our own cached copy over system-installed versions because
    system copies (e.g. from homebrew) may be outdated and not support
    newer model architectures like Gemma-3.
    """
    # Check cached first (our latest download)
    cached = CONVERTER_DIR / script_name
    if cached.exists():
        return str(cached)

    # Auto-download from GitHub (latest version)
    print(f"[convert] Downloading {script_name} from llama.cpp...", flush=True)
    try:
        import urllib.request

        CONVERTER_DIR.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(url, headers={"User-Agent": "pratibmb/0.1"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            cached.write_bytes(resp.read())

        print(f"[convert] Cached at {cached}", flush=True)

        # Also download the companion script if needed
        # convert_lora_to_gguf.py imports convert_hf_to_gguf
        companion = None
        if script_name == "convert_lora_to_gguf.py":
            companion = ("convert_hf_to_gguf.py", HF_TO_GGUF_URL)
        elif script_name == "convert_hf_to_gguf.py":
            companion = ("convert_lora_to_gguf.py", LORA_TO_GGUF_URL)

        if companion:
            comp_name, comp_url = companion
            comp_path = CONVERTER_DIR / comp_name
            if not comp_path.exists():
                print(f"[convert] Also downloading {comp_name}...", flush=True)
                req2 = urllib.request.Request(
                    comp_url, headers={"User-Agent": "pratibmb/0.1"}
                )
                with urllib.request.urlopen(req2, timeout=60) as resp2:
                    comp_path.write_bytes(resp2.read())

        return str(cached)

    except Exception as e:
        print(f"[convert] Could not download {script_name}: {e}", flush=True)

    # Fall back to local installations (may be outdated)
    local = _find_local_converter(script_name)
    if local:
        return local

    return None


def _ensure_gguf_package() -> None:
    """Ensure the 'gguf' pip package is installed (from llama.cpp GitHub).

    We install from GitHub rather than PyPI because the converter scripts
    are downloaded from GitHub master and need the matching gguf package
    (PyPI releases sometimes lag behind the converter scripts).
    """
    try:
        import gguf  # noqa: F401
        # Verify it has the model architectures we need
        if hasattr(gguf, "MODEL_ARCH") and hasattr(gguf.MODEL_ARCH, "GEMMA3"):
            return
    except ImportError:
        pass

    print("[convert] Installing/updating gguf package from llama.cpp...", flush=True)
    subprocess.run(
        [
            sys.executable, "-m", "pip", "install", "--force-reinstall",
            "gguf @ git+https://github.com/ggerganov/llama.cpp#subdirectory=gguf-py",
            "--quiet",
        ],
        capture_output=True,
        timeout=120,
    )


def _ensure_torch() -> bool:
    """Ensure torch is available for GGUF conversion.

    On macOS, installs CPU-only torch (~200 MB). Returns True if available.
    """
    try:
        import torch  # noqa: F401
        return True
    except ImportError:
        pass

    print(
        "[convert] torch not installed — required for GGUF conversion.",
        flush=True,
    )
    print(
        "[convert] Installing torch (CPU-only, ~200 MB)...",
        flush=True,
    )
    result = subprocess.run(
        [
            sys.executable, "-m", "pip", "install",
            "torch", "--quiet",
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        print(f"[convert] Failed to install torch: {result.stderr[-500:]}", flush=True)
        return False

    print("[convert] torch installed successfully", flush=True)
    return True


def _run_converter(
    converter: str,
    args: list[str],
) -> dict[str, Any]:
    """Run a converter script with the given arguments."""
    cmd = [sys.executable, converter] + args
    print(f"[convert] Running: {' '.join(cmd[:4])}...", flush=True)

    # Add our tools dir to PYTHONPATH so scripts can import each other
    # (convert_lora_to_gguf.py imports convert_hf_to_gguf)
    env = os.environ.copy()
    converter_dir = str(Path(converter).parent)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{converter_dir}:{existing}" if existing else converter_dir

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=600, env=env,
        )
        if result.returncode != 0:
            return {
                "status": "error",
                "error": f"Conversion failed:\n{result.stderr[-2000:]}",
                "stdout": result.stdout[-1000:] if result.stdout else "",
            }
        return {"status": "ok"}
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "Conversion timed out after 10 min."}
    except FileNotFoundError:
        return {"status": "error", "error": f"Python not found: {sys.executable}"}


# ── Cleanup ─────────────────────────────────────────────────────────────

def _safe_cleanup(path: Path) -> None:
    """Remove a directory tree, ignoring errors."""
    try:
        shutil.rmtree(path)
        print(f"[convert] Cleaned up {path}", flush=True)
    except Exception as e:
        print(f"[convert] Warning: could not clean up {path}: {e}", flush=True)


# ── Manual instructions ─────────────────────────────────────────────────

def _manual_instructions(
    adapter_dir: Path,
    output_path: Path,
    base_model: str,
    errors: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Return instructions for manual conversion."""
    error_log = ""
    if errors:
        error_log = "\nAutomatic conversion could not complete:\n"
        for method, err in errors:
            # Keep it concise — first line only
            first_line = err.strip().split("\n")[-1][:120]
            error_log += f"  - {method}: {first_line}\n"

    instructions = f"""{error_log}
Two options to convert your adapter to GGUF:

=== Option 1: MLX-LM fuse + llama.cpp convert (macOS) ===
# Fuse adapter into base model
python -m mlx_lm fuse \\
  --model {base_model} \\
  --adapter-path {adapter_dir} \\
  --save-path {adapter_dir.parent / 'fused_model'}

# Convert fused model to GGUF
pip install gguf
git clone --depth 1 https://github.com/ggerganov/llama.cpp ~/llama.cpp
python ~/llama.cpp/convert_hf_to_gguf.py \\
  --outtype f16 \\
  --outfile {output_path} \\
  {adapter_dir.parent / 'fused_model'}

=== Option 2: llama.cpp LoRA converter (any platform) ===
git clone --depth 1 https://github.com/ggerganov/llama.cpp ~/llama.cpp
pip install gguf
python ~/llama.cpp/convert_lora_to_gguf.py \\
  --base {base_model} \\
  --outfile {output_path.with_name('adapter.gguf')} \\
  {adapter_dir}

The GGUF file will be auto-detected at next chat launch.
""".strip()

    return {
        "status": "manual",
        "instructions": instructions,
        "adapter_dir": str(adapter_dir),
        "output_path": str(output_path),
    }
