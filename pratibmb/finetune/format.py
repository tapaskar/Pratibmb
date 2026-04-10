"""
Format extracted pairs into Gemma chat template for LoRA training.

Gemma 3 chat format:
    <start_of_turn>user
    {user message}<end_of_turn>
    <start_of_turn>model
    {model response}<end_of_turn>

We put thread context + prompt into the user turn, and the completion
into the model turn. The system instruction is baked into the user
turn prefix since Gemma uses user/model turns only.
"""
from __future__ import annotations

import json
from pathlib import Path


# System preamble baked into every user turn
_SYSTEM_PREAMBLE = (
    "You are replying as yourself in a casual text conversation. "
    "Reply naturally and in character. Keep it short (1-4 sentences)."
)


def format_for_gemma(
    pairs: list[dict],
    include_system: bool = True,
) -> list[dict]:
    """Convert training pairs to Gemma chat-formatted records.

    Each record has a 'text' field containing the full formatted
    conversation, ready for tokenization by mlx-lm.

    Args:
        pairs: Output of extract_pairs().
        include_system: Whether to include the system preamble.

    Returns:
        List of dicts with 'text' key (formatted string) plus metadata.
    """
    records: list[dict] = []

    for pair in pairs:
        user_parts: list[str] = []

        if include_system:
            user_parts.append(_SYSTEM_PREAMBLE)
            user_parts.append("")

        # Add thread context if available
        if pair.get("context"):
            user_parts.append("[Previous messages]")
            user_parts.append(pair["context"])
            user_parts.append("")

        # The prompt message
        prompt_author = pair.get("prompt_author", "Friend")
        user_parts.append(f"{prompt_author}: {pair['prompt']}")

        user_text = "\n".join(user_parts)
        model_text = pair["completion"]

        # Full formatted text
        formatted = (
            f"<start_of_turn>user\n"
            f"{user_text}<end_of_turn>\n"
            f"<start_of_turn>model\n"
            f"{model_text}<end_of_turn>"
        )

        records.append({
            "text": formatted,
            "thread_name": pair.get("thread_name", ""),
            "timestamp": pair.get("timestamp", ""),
        })

    return records


def save_jsonl(records: list[dict], output_path: Path) -> int:
    """Save formatted records to a JSONL file for training.

    Each line contains {"text": "..."} which is the standard format
    expected by mlx-lm fine-tuning.

    Args:
        records: Output of format_for_gemma().
        output_path: Path to write the .jsonl file.

    Returns:
        Number of records written.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for rec in records:
            # Only write the text field for training
            line = json.dumps({"text": rec["text"]}, ensure_ascii=False)
            f.write(line + "\n")

    return len(records)


def split_dataset(
    records: list[dict],
    train_ratio: float = 0.9,
) -> tuple[list[dict], list[dict]]:
    """Split records into train and validation sets.

    Args:
        records: Full list of formatted records.
        train_ratio: Fraction for training (rest goes to validation).

    Returns:
        (train_records, val_records) tuple.
    """
    split_idx = int(len(records) * train_ratio)
    return records[:split_idx], records[split_idx:]
