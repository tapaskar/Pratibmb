"""
LoRA fine-tuning pipeline for Pratibmb.

Extracts conversational pairs from the message corpus, formats them for
Gemma chat fine-tuning, trains a LoRA adapter via MLX-LM, and converts
the result to GGUF for llama-cpp-python inference.
"""
from .pairs import extract_pairs
from .format import format_for_gemma, save_jsonl
from .train import train_lora, TrainConfig
from .convert import convert_adapter

__all__ = [
    "extract_pairs",
    "format_for_gemma",
    "save_jsonl",
    "train_lora",
    "TrainConfig",
    "convert_adapter",
]
