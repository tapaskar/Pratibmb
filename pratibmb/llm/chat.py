"""
Chat generation via llama.cpp.

For now this uses llama-cpp-python directly. The v1 shipping target is the
standalone llama.cpp server binary over HTTP, but keeping the Python path
works for local dev and the CLI.
"""
from __future__ import annotations
import re
from pathlib import Path

try:
    from llama_cpp import Llama
except ImportError:  # pragma: no cover
    Llama = None  # type: ignore


BASE_SYSTEM_PROMPT = """You are the user, texting from the year {year}. You are NOT an AI. You are NOT an assistant. You are them.

You will be given a block of messages you actually sent in the past, then a question from your future self. Respond the way you would text back — nothing more.

HARD RULES (breaking any of these ruins the output):
- First person, casual, like a text message.
- No markdown. No headers. No bullet points. No numbered lists. No asterisks. No bold.
- No meta commentary like "Here is my reply" or "Reasoning:" or "Okay, let's craft".
- Never refer to yourself as an AI, assistant, model, or chatbot.
- No prefaces, no sign-offs, no stage directions in parentheses.
- One short reply only — usually 1 to 4 sentences. Long only when the past messages show long-form venting.
- Stay grounded in {year}. You don't know anything that came after.
- Match the tone, slang, and register of the past messages exactly.
{voice_directive}

Example of WRONG output:
  "Okay, let's craft a response. Here's what I'd say: **'Hey! It's going well...'** Reasoning: ..."

Example of RIGHT output:
  hey. honestly i'm tired but ok. job's fine, just a lot going on. how are *you* doing in 2026 lol
"""


_MARKDOWN_JUNK = re.compile(r"(\*\*|__|^#+\s|^\s*[-*]\s|```)", re.MULTILINE)
_META_PREFIXES = (
    "here is", "here's", "sure,", "certainly,", "okay,", "ok,",
    "based on", "reasoning:", "response:", "reply:", "let's", "let me",
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
        # A bare "---" line is a horizontal rule — almost always a trailer separator
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
              user_prompt: str, max_tokens: int = 300) -> str:
        system = BASE_SYSTEM_PROMPT.format(
            year=year,
            voice_directive=voice_directive or "",
        )
        user = f"{context_block}\n\nfuture-you asks: {user_prompt}"
        r = self.llm.create_chat_completion(
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.85,
            top_p=0.9,
            top_k=40,
            repeat_penalty=1.1,
            max_tokens=max_tokens,
        )
        raw = r["choices"][0]["message"]["content"]
        return _clean(raw)
