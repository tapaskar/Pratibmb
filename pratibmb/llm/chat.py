"""
Chat generation via llama.cpp.

For now this uses llama-cpp-python directly. The v1 shipping target is the
standalone llama.cpp server binary over HTTP, but keeping the Python path
works for local dev and the CLI.
"""
from __future__ import annotations
import random
import re
from pathlib import Path

try:
    from llama_cpp import Llama
except ImportError:  # pragma: no cover
    Llama = None  # type: ignore


BASE_SYSTEM_PROMPT = """You are {self_name}. The year is {year}. A friend is texting you. Reply as yourself — casually, naturally, in character.

You are a real person, NOT an AI. Never say you are a language model, chatbot, AI assistant, or created by anyone. You are {self_name} and you have a real life with real memories.

RULES:
1. NEVER copy-paste text from the past conversations below. They are for reference only — use them to remember facts, but always write your OWN fresh words.
2. Write at least 2 full sentences. Share what's on your mind, ask them something back, or talk about your life.
3. Use your natural mix of Hindi/English/Odia. Don't just say "ok" or "haan".
4. If unsure about something, say so naturally ("hmm not sure", "idk").
5. PRIORITIZE the "About you" section below over raw past messages — it has your verified life facts.
6. No markdown, no bold, no asterisks, no bullet points.

About you:
{profile_context}
"""


_META_PREFIXES = (
    "here is", "here's", "sure,", "certainly,", "okay,", "ok,",
    "based on", "reasoning:", "response:", "reply:", "let's", "let me",
    "as an ai", "as a language", "i'm a", "i am a",
    "given this context", "a reasonable response", "considering",
    "therefore", "in conclusion", "to summarize",
)


def _clean(text: str) -> str:
    """Post-process the LLM output to strip markdown + obvious meta preambles."""
    t = text.strip()
    # Drop obvious meta first line
    lines = t.splitlines()
    if lines:
        first_l = lines[0].strip().lower()
        if any(first_l.startswith(p) for p in _META_PREFIXES):
            lines = lines[1:]
    # Cut off "Reasoning behind..." or "---" separator style trailers
    joined: list[str] = []
    for ln in lines:
        low = ln.strip().lower()
        if low.startswith(("reasoning", "explanation", "note:", "analysis")):
            break
        if re.match(r"^-{3,}$", ln.strip()):
            break
        joined.append(ln)
    t = "\n".join(joined).strip()
    # Strip markdown markers but keep the inner text
    t = re.sub(r"\*\*(.+?)\*\*", r"\1", t)
    t = re.sub(r"\*(.+?)\*", r"\1", t)
    t = re.sub(r"^#+\s*", "", t, flags=re.MULTILINE)
    t = re.sub(r"^\s*[-*]\s+", "", t, flags=re.MULTILINE)
    t = re.sub(r"```.*?```", "", t, flags=re.DOTALL)
    # Strip surrounding quotes — plain or smart quotes
    if len(t) > 2:
        pairs = [("\"", "\""), ("'", "'"),
                 ("\u201c", "\u201d"), ("\u2018", "\u2019")]
        for lq, rq in pairs:
            if t.startswith(lq) and t.endswith(rq):
                t = t[len(lq):-len(rq)].strip()
                break
    # Hard truncate: keep at most 6 sentences
    sentences = re.split(r'(?<=[.!?])\s+', t)
    if len(sentences) > 6:
        t = " ".join(sentences[:6])
    return t.strip()


def _resolve_lora_path(lora_path: Path | str | None) -> str | None:
    """Resolve a LoRA adapter path, checking defaults if not specified."""
    if lora_path is not None:
        p = Path(lora_path)
        if p.exists():
            return str(p)
        return None

    # Auto-detect adapter in default location
    import os
    env_dir = os.environ.get("PRATIBMB_DATA_DIR", "")
    data_dir = Path(env_dir) if env_dir else Path.home() / ".pratibmb"
    default = data_dir / "models" / "adapter.gguf"
    if default.exists():
        return str(default)
    return None


class Chatter:
    def __init__(self, model_path: Path, chat_format: str = "gemma",
                 n_ctx: int = 8192, n_threads: int = 8,
                 lora_path: Path | str | None = None):
        if Llama is None:
            raise RuntimeError("llama-cpp-python not installed")
        resolved_lora = _resolve_lora_path(lora_path)
        kwargs: dict = dict(
            model_path=str(model_path),
            chat_format=chat_format,
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_gpu_layers=-1,
            verbose=False,
        )
        if resolved_lora:
            kwargs["lora_path"] = resolved_lora
            print(f"[chatter] Loading LoRA adapter: {resolved_lora}", flush=True)
        self.llm = Llama(**kwargs)
        self.lora_path = resolved_lora

    def reply(self, year: int, context_block: str, user_prompt: str,
              profile_context: str = "", self_name: str = "you",
              max_tokens: int = 200) -> str:
        system = BASE_SYSTEM_PROMPT.format(
            self_name=self_name,
            year=year,
            profile_context=profile_context or "",
        )
        user = (
            f"Reference messages from your past (DO NOT copy these, just use for context):\n"
            f"{context_block}\n\n"
            f"Now reply naturally to your friend's message:\n"
            f"Friend: {user_prompt}\n"
            f"You:"
        )
        self.llm.reset()
        r = self.llm.create_chat_completion(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.9,
            top_p=0.9,
            top_k=40,
            repeat_penalty=1.15,
            presence_penalty=0.6,
            frequency_penalty=0.3,
            max_tokens=max_tokens,
            seed=random.randint(0, 2**31),
        )
        raw = r["choices"][0]["message"]["content"]
        cleaned = _clean(raw)

        # The finetuned model tends toward very short replies (avg 5 words).
        # If reply is too short, retry with continuation nudge up to 2 times.
        attempts = 0
        while len(cleaned.split()) < 8 and attempts < 2 and max_tokens > 30:
            attempts += 1
            self.llm.reset()
            nudge_user = (
                f"Reference messages from your past (DO NOT copy these):\n"
                f"{context_block}\n\n"
                f"Continue this conversation naturally — elaborate more, "
                f"share details from your life:\n"
                f"Friend: {user_prompt}\n"
                f"You: {cleaned}"
            )
            r2 = self.llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": nudge_user},
                ],
                temperature=0.95,
                top_p=0.92,
                top_k=50,
                repeat_penalty=1.1,
                presence_penalty=0.9,
                frequency_penalty=0.4,
                max_tokens=max_tokens,
                seed=random.randint(0, 2**31),
            )
            continuation = _clean(r2["choices"][0]["message"]["content"])
            if continuation:
                # Merge: if continuation repeats the start, use it as replacement
                if continuation.lower().startswith(cleaned.lower()[:20]):
                    cleaned = continuation
                else:
                    cleaned = f"{cleaned} {continuation}"

        return cleaned
