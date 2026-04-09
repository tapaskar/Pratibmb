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


BASE_SYSTEM_PROMPT = """Continue this text conversation. You are the sender of the past messages shown below. Year: {year}.
{voice_directive}
STRICT:
- Reply with 1 short text (max 15 words). Never write more than 2 sentences.
- ONLY mention things from your past messages. NEVER invent names, places, jobs, or facts.
- If you don't know, say "idk" or "not sure".
- No markdown. No asterisks. No bullet points.
- Match the language/style of your past messages exactly.
- You are NOT an AI. You are a real person texting a friend.
"""


_MARKDOWN_JUNK = re.compile(r"(\*\*|__|^#+\s|^\s*[-*]\s|```)", re.MULTILINE)
_META_PREFIXES = (
    "here is", "here's", "sure,", "certainly,", "okay,", "ok,",
    "based on", "reasoning:", "response:", "reply:", "let's", "let me",
    "as an ai", "as a language", "i'm a", "i am a",
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
    # Hard truncate: keep at most 2 sentences
    sentences = re.split(r'(?<=[.!?])\s+', t)
    if len(sentences) > 2:
        t = " ".join(sentences[:2])
    return t.strip()


class Chatter:
    def __init__(self, model_path: Path, chat_format: str = "gemma",
                 n_ctx: int = 8192, n_threads: int = 8):
        if Llama is None:
            raise RuntimeError("llama-cpp-python not installed")
        self.llm = Llama(
            model_path=str(model_path),
            chat_format=chat_format,
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_gpu_layers=-1,
            verbose=False,
        )

    def reply(self, year: int, voice_directive: str, context_block: str,
              user_prompt: str, max_tokens: int = 40) -> str:
        system = BASE_SYSTEM_PROMPT.format(
            year=year,
            voice_directive=voice_directive or "",
        )
        user = (
            f"Your past messages for reference:\n{context_block}\n\n"
            f"Friend's message: {user_prompt}\n"
            f"Your reply (short, casual):"
        )
        self.llm.reset()  # clear KV cache between turns
        r = self.llm.create_chat_completion(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.7,
            top_p=0.85,
            top_k=30,
            repeat_penalty=1.2,
            max_tokens=max_tokens,
            seed=random.randint(0, 2**31),
        )
        raw = r["choices"][0]["message"]["content"]
        return _clean(raw)
