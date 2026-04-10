"""
LoRA training wrapper using MLX-LM.

MLX-LM is an optional dependency — if not installed, we provide clear
instructions for manual setup. This module handles:
  - Configuring LoRA hyperparameters (rank, alpha, target modules)
  - Setting up training data paths
  - Running training via mlx-lm's fine-tuning API
  - Saving adapter weights

The trained adapter is in MLX format and needs conversion to GGUF
(see convert.py) before llama-cpp-python can load it.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


@dataclass
class TrainConfig:
    """LoRA training configuration."""

    # Model
    model_name: str = "google/gemma-3-4b-it"

    # LoRA
    lora_rank: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    lora_target_modules: list[str] = field(
        default_factory=lambda: ["q_proj", "v_proj", "k_proj", "o_proj"]
    )

    # Training
    num_epochs: int = 2
    batch_size: int = 1
    grad_accum_steps: int = 4
    learning_rate: float = 1e-4
    warmup_steps: int = 50
    max_seq_length: int = 512

    # Paths (defaults under ~/.pratibmb)
    data_dir: str = ""  # set at runtime
    output_dir: str = ""  # set at runtime

    # Steps
    steps_per_eval: int = 50
    save_every: int = 100
    max_steps: int = -1  # -1 = use epochs

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def resolve_paths(self) -> None:
        """Fill in default paths if not set."""
        env_dir = os.environ.get("PRATIBMB_DATA_DIR", "")
        base = Path(env_dir) if env_dir else Path.home() / ".pratibmb"
        if not self.data_dir:
            self.data_dir = str(base / "finetune" / "data")
        if not self.output_dir:
            self.output_dir = str(base / "finetune" / "adapter")


def check_mlx_available() -> bool:
    """Check if mlx-lm is importable."""
    try:
        import mlx_lm  # noqa: F401
        return True
    except ImportError:
        return False


def _write_mlx_config(config: TrainConfig, config_path: Path) -> None:
    """Write mlx-lm LoRA config JSON matching CONFIG_DEFAULTS format."""
    # Calculate iters from epochs if max_steps not set
    # mlx-lm uses iters, not epochs — estimate from data size
    iters = config.max_steps
    if iters <= 0:
        # Estimate: count lines in train.jsonl
        train_file = Path(config.data_dir) / "train.jsonl"
        if train_file.exists():
            n_samples = sum(1 for _ in open(train_file))
            effective_batch = config.batch_size * config.grad_accum_steps
            iters_per_epoch = max(1, n_samples // effective_batch)
            iters = iters_per_epoch * config.num_epochs
        else:
            iters = 1000  # fallback

    cfg = {
        "model": config.model_name,
        "train": True,
        "data": config.data_dir,
        "adapter_path": config.output_dir,
        "fine_tune_type": "lora",
        "num_layers": -1,  # all layers
        "batch_size": config.batch_size,
        "iters": iters,
        "learning_rate": config.learning_rate,
        "steps_per_report": 10,
        "steps_per_eval": config.steps_per_eval,
        "save_every": config.save_every,
        "max_seq_length": config.max_seq_length,
        "grad_checkpoint": True,
        "grad_accumulation_steps": config.grad_accum_steps,
        "lora_parameters": {
            "rank": config.lora_rank,
            "dropout": config.lora_dropout,
            "scale": float(config.lora_alpha),
        },
        "mask_prompt": False,
        "seed": 42,
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(cfg, indent=2))


def train_lora(
    config: TrainConfig | None = None,
    progress_callback: Any = None,
) -> dict[str, Any]:
    """Run LoRA fine-tuning.

    Args:
        config: Training configuration. Uses defaults if None.
        progress_callback: Optional callable(step, loss) for progress.

    Returns:
        Dict with status, adapter_path, and training details.
    """
    if config is None:
        config = TrainConfig()
    config.resolve_paths()

    data_dir = Path(config.data_dir)
    output_dir = Path(config.output_dir)

    # Verify training data exists
    train_file = data_dir / "train.jsonl"
    if not train_file.exists():
        return {
            "status": "error",
            "error": (
                f"Training data not found at {train_file}. "
                "Run `pratibmb finetune extract-pairs` first."
            ),
        }

    if not check_mlx_available():
        return _manual_instructions(config)

    # Run training via mlx-lm CLI (most reliable approach)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Write config file
    config_path = data_dir / "train_config.json"
    _write_mlx_config(config, config_path)

    # Build mlx-lm command — use config file for LoRA params
    # (CLI doesn't expose --lora-rank or --num-epochs directly)
    cmd = [
        sys.executable, "-m", "mlx_lm.lora",
        "-c", str(config_path),
    ]

    print(f"[finetune] Running: {' '.join(cmd)}", flush=True)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=7200,  # 2 hour timeout
        )
        if result.returncode != 0:
            return {
                "status": "error",
                "error": f"mlx-lm training failed:\n{result.stderr}",
                "stdout": result.stdout,
            }

        return {
            "status": "ok",
            "adapter_path": str(output_dir),
            "stdout": result.stdout,
            "config": config.to_dict(),
        }

    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "error": "Training timed out after 2 hours.",
        }
    except FileNotFoundError:
        return _manual_instructions(config)


def _manual_instructions(config: TrainConfig) -> dict[str, Any]:
    """Return instructions for manual training when mlx-lm is unavailable."""
    instructions = f"""
mlx-lm is not installed. To train the LoRA adapter manually:

1. Install mlx-lm:
   pip install mlx-lm

2. Run training:
   python -m mlx_lm.lora \\
     --model {config.model_name} \\
     --data {config.data_dir} \\
     --adapter-path {config.output_dir} \\
     --train \\
     --batch-size {config.batch_size} \\
     --num-epochs {config.num_epochs} \\
     --learning-rate {config.learning_rate} \\
     --lora-rank {config.lora_rank} \\
     --max-seq-length {config.max_seq_length}

3. Convert the adapter to GGUF:
   pratibmb finetune convert --adapter-dir {config.output_dir}

Training data is at: {config.data_dir}/train.jsonl
""".strip()

    return {
        "status": "manual",
        "instructions": instructions,
        "config": config.to_dict(),
    }
