"""
LoRA training wrapper — supports MLX (macOS) and PyTorch (Windows/Linux).

Detects the available backend automatically:
  - macOS Apple Silicon: MLX-LM (native Metal acceleration)
  - Windows/Linux with NVIDIA GPU: PyTorch + PEFT + QLoRA
  - CPU-only: PyTorch without quantization (slower but works)

The trained adapter needs conversion to GGUF (see convert.py) before
llama-cpp-python can load it.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


def detect_backend() -> str:
    """Detect the best available training backend."""
    try:
        import mlx_lm  # noqa: F401
        return "mlx"
    except ImportError:
        pass
    try:
        import torch  # noqa: F401
        return "pytorch"
    except ImportError:
        pass
    return "none"


@dataclass
class TrainConfig:
    """LoRA training configuration."""

    # Model — defaults depend on backend (set in resolve_paths)
    model_name: str = ""

    # LoRA — conservative settings to avoid divergence
    lora_rank: int = 8
    lora_alpha: int = 16
    lora_dropout: float = 0.05
    lora_target_modules: list[str] = field(
        default_factory=lambda: ["q_proj", "v_proj", "k_proj", "o_proj"]
    )

    # Training
    num_epochs: int = 2
    batch_size: int = 1
    grad_accum_steps: int = 4
    learning_rate: float = 2e-5
    warmup_steps: int = 50
    max_seq_length: int = 512

    # Paths (defaults under ~/.pratibmb)
    data_dir: str = ""
    output_dir: str = ""

    # Backend: "auto", "mlx", "pytorch"
    backend: str = "auto"

    # Steps
    steps_per_eval: int = 50
    save_every: int = 100
    max_steps: int = -1  # -1 = use epochs

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def resolve_paths(self) -> None:
        """Fill in default paths and model name if not set."""
        env_dir = os.environ.get("PRATIBMB_DATA_DIR", "")
        base = Path(env_dir) if env_dir else Path.home() / ".pratibmb"
        if not self.data_dir:
            self.data_dir = str(base / "finetune" / "data")
        if not self.output_dir:
            self.output_dir = str(base / "finetune" / "adapter")
        if not self.model_name:
            backend = self.backend if self.backend != "auto" else detect_backend()
            if backend == "mlx":
                self.model_name = "mlx-community/gemma-3-4b-it-8bit"
            else:
                self.model_name = "google/gemma-3-4b-it"


def train_lora(
    config: TrainConfig | None = None,
    progress_callback: Any = None,
) -> dict[str, Any]:
    """Run LoRA fine-tuning using the best available backend.

    Returns dict with status, adapter_path, and training details.
    """
    if config is None:
        config = TrainConfig()
    config.resolve_paths()

    # Verify training data exists
    train_file = Path(config.data_dir) / "train.jsonl"
    if not train_file.exists():
        return {
            "status": "error",
            "error": (
                f"Training data not found at {train_file}. "
                "Run `pratibmb finetune extract-pairs` first."
            ),
        }

    # Resolve backend
    backend = config.backend
    if backend == "auto":
        backend = detect_backend()

    if backend == "mlx":
        return _train_mlx(config)
    elif backend == "pytorch":
        return _train_pytorch(config)
    else:
        return _manual_instructions(config)


# ---- MLX Backend (macOS Apple Silicon) ------------------------------------

def _write_mlx_config(config: TrainConfig, config_path: Path) -> None:
    """Write mlx-lm LoRA config JSON."""
    iters = config.max_steps
    if iters <= 0:
        train_file = Path(config.data_dir) / "train.jsonl"
        if train_file.exists():
            n_samples = sum(1 for _ in open(train_file))
            effective_batch = config.batch_size * config.grad_accum_steps
            iters_per_epoch = max(1, n_samples // effective_batch)
            iters = iters_per_epoch * config.num_epochs
        else:
            iters = 1000

    cfg = {
        "model": config.model_name,
        "train": True,
        "data": config.data_dir,
        "adapter_path": config.output_dir,
        "fine_tune_type": "lora",
        "num_layers": 16,
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


def _train_mlx(config: TrainConfig) -> dict[str, Any]:
    """Train using MLX-LM on macOS Apple Silicon."""
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    config_path = Path(config.data_dir) / "train_config.json"
    _write_mlx_config(config, config_path)

    cmd = [sys.executable, "-m", "mlx_lm.lora", "-c", str(config_path)]
    print(f"[finetune:mlx] Running: {' '.join(cmd)}", flush=True)

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=7200,
        )
        if result.returncode != 0:
            return {
                "status": "error",
                "error": f"mlx-lm training failed:\n{result.stderr}",
                "stdout": result.stdout,
            }
        return {
            "status": "ok",
            "backend": "mlx",
            "adapter_path": str(output_dir),
            "stdout": result.stdout,
            "config": config.to_dict(),
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "Training timed out after 2 hours."}
    except FileNotFoundError:
        return _manual_instructions(config)


# ---- PyTorch Backend (Windows / Linux) ------------------------------------

def _train_pytorch(config: TrainConfig) -> dict[str, Any]:
    """Train using PyTorch + PEFT + QLoRA on Windows/Linux."""
    try:
        import torch
    except ImportError:
        return {
            "status": "error",
            "error": "PyTorch not installed. Run: pip install 'pratibmb[finetune-pytorch]'",
        }

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check for PEFT and transformers
    missing = []
    for pkg in ["transformers", "peft", "trl", "datasets"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        return {
            "status": "error",
            "error": (
                f"Missing packages: {', '.join(missing)}. "
                "Run: pip install 'pratibmb[finetune-pytorch]'"
            ),
        }

    # Build and run training script as subprocess for isolation
    script = _pytorch_train_script(config)
    script_path = Path(config.data_dir) / "train_pytorch.py"
    script_path.write_text(script)

    cmd = [sys.executable, str(script_path)]
    print(f"[finetune:pytorch] Running: {' '.join(cmd)}", flush=True)

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=14400,  # 4 hours
        )
        if result.returncode != 0:
            return {
                "status": "error",
                "error": f"PyTorch training failed:\n{result.stderr[-2000:]}",
                "stdout": result.stdout[-2000:],
            }
        return {
            "status": "ok",
            "backend": "pytorch",
            "adapter_path": str(output_dir),
            "stdout": result.stdout[-2000:],
            "config": config.to_dict(),
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "error": "Training timed out after 4 hours."}


def _pytorch_train_script(config: TrainConfig) -> str:
    """Generate a self-contained PyTorch training script."""
    return f'''#!/usr/bin/env python3
"""Auto-generated PyTorch LoRA training script for Pratibmb."""
import json
import torch
from pathlib import Path
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
)
from peft import LoraConfig, get_peft_model, TaskType
from trl import SFTTrainer

# Config
MODEL_NAME = "{config.model_name}"
DATA_DIR = "{config.data_dir}"
OUTPUT_DIR = "{config.output_dir}"
RANK = {config.lora_rank}
ALPHA = {config.lora_alpha}
DROPOUT = {config.lora_dropout}
LR = {config.learning_rate}
EPOCHS = {config.num_epochs}
BATCH_SIZE = {config.batch_size}
GRAD_ACCUM = {config.grad_accum_steps}
MAX_SEQ_LEN = {config.max_seq_length}

print("[pytorch] Loading model...", flush=True)

# Load model — use 4-bit quantization if bitsandbytes is available
try:
    from transformers import BitsAndBytesConfig
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME, quantization_config=bnb_config,
        device_map="auto", trust_remote_code=True,
    )
    print("[pytorch] Using 4-bit QLoRA (bitsandbytes)", flush=True)
except (ImportError, Exception) as e:
    print(f"[pytorch] bitsandbytes not available ({{e}}), using fp16", flush=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME, torch_dtype=torch.float16,
        device_map="auto", trust_remote_code=True,
    )

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token

# LoRA config
lora_config = LoraConfig(
    r=RANK,
    lora_alpha=ALPHA,
    lora_dropout=DROPOUT,
    target_modules={config.lora_target_modules},
    task_type=TaskType.CAUSAL_LM,
)

model = get_peft_model(model, lora_config)
model.print_trainable_parameters()

# Load data
dataset = load_dataset("json", data_files={{
    "train": str(Path(DATA_DIR) / "train.jsonl"),
    "validation": str(Path(DATA_DIR) / "valid.jsonl"),
}})

print(f"[pytorch] Train: {{len(dataset['train'])}}, Val: {{len(dataset['validation'])}}", flush=True)

# Training args
training_args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    num_train_epochs=EPOCHS,
    per_device_train_batch_size=BATCH_SIZE,
    gradient_accumulation_steps=GRAD_ACCUM,
    learning_rate=LR,
    warmup_steps={config.warmup_steps},
    logging_steps=10,
    eval_strategy="steps",
    eval_steps=50,
    save_strategy="steps",
    save_steps=100,
    max_grad_norm=1.0,
    bf16=torch.cuda.is_available() and torch.cuda.is_bf16_supported(),
    fp16=torch.cuda.is_available() and not torch.cuda.is_bf16_supported(),
    gradient_checkpointing=True,
    report_to="none",
    max_seq_length=MAX_SEQ_LEN,
)

# Train
trainer = SFTTrainer(
    model=model,
    train_dataset=dataset["train"],
    eval_dataset=dataset["validation"],
    args=training_args,
    dataset_text_field="text",
    max_seq_length=MAX_SEQ_LEN,
)

print("[pytorch] Starting training...", flush=True)
trainer.train()

# Save
print(f"[pytorch] Saving adapter to {{OUTPUT_DIR}}", flush=True)
model.save_pretrained(OUTPUT_DIR)
tokenizer.save_pretrained(OUTPUT_DIR)
print("[pytorch] Done!", flush=True)
'''


# ---- Manual Instructions -------------------------------------------------

def _manual_instructions(config: TrainConfig) -> dict[str, Any]:
    """Return instructions for manual training."""
    instructions = f"""
No training backend found. Install one of:

=== macOS (Apple Silicon) — MLX ===
pip install mlx-lm
pratibmb finetune train

=== Windows / Linux — PyTorch ===
pip install 'pratibmb[finetune-pytorch]'
pratibmb finetune train

=== Manual PyTorch training ===
pip install torch transformers peft trl datasets bitsandbytes

python -c "
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model
from trl import SFTTrainer
# ... see docs/HELP.md for full script
"

Training data is at: {config.data_dir}/train.jsonl
""".strip()

    return {
        "status": "manual",
        "instructions": instructions,
        "config": config.to_dict(),
    }
