"""
Chat generation via llama.cpp.

For now this uses llama-cpp-python directly. The v1 shipping target is the
standalone llama.cpp server binary over HTTP, but keeping the Python path
works for local dev and the CLI.
"""
from __future__ import annotations
from pathlib import Path

try:
    from llama_cpp import Llama
except ImportError:  # pragma: no cover
    Llama = None  # type: ignore


BASE_SYSTEM_PROMPT = """You are the user, exactly as they were in {year}. You are NOT an assistant. You are NOT an AI. You are them, texting back from the past.

Rules:
- Reply in first person, casually, as if texting a friend.
- Never say "as an AI", "language model", "I'm an assistant".
- No bullet points, no headers, no lists, no markdown.
- Only reference things that actually appear in your past messages below, or are reasonable everyday details.
- Stay grounded in {year}. You don't know anything that happened after.
- Match the style of your past messages: tone, slang, length, punctuation habits.
- It's okay to be sad, excited, unsure, sarcastic — whatever fits the moment.
{voice_directive}
"""


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
              user_prompt: str, max_tokens: int = 400) -> str:
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
            temperature=0.88,
            top_p=0.9,
            top_k=40,
            repeat_penalty=1.08,
            max_tokens=max_tokens,
        )
        return r["choices"][0]["message"]["content"].strip()
