"""
Embedding via llama.cpp (GGUF embedding model).

We use a small GGUF embedding model (e.g. bge-small-en-v1.5.Q4_K_M.gguf) so
the runtime stack is 100% llama.cpp — no Python ML deps in the shipped app.
"""
from __future__ import annotations
from pathlib import Path
from typing import Iterable
import numpy as np

try:
    from llama_cpp import Llama
except ImportError:  # pragma: no cover
    Llama = None  # type: ignore


class Embedder:
    """Thin wrapper around llama.cpp's embedding mode."""

    def __init__(self, model_path: Path, n_ctx: int = 512, n_threads: int = 8):
        if Llama is None:
            raise RuntimeError("llama-cpp-python not installed")
        self.llm = Llama(
            model_path=str(model_path),
            embedding=True,
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_gpu_layers=-1,
            verbose=False,
        )

    def embed(self, texts: Iterable[str]) -> np.ndarray:
        vecs: list[np.ndarray] = []
        for t in texts:
            t = (t or "").strip() or " "
            r = self.llm.create_embedding(t)
            v = np.asarray(r["data"][0]["embedding"], dtype=np.float32)
            n = np.linalg.norm(v)
            if n > 0:
                v = v / n
            vecs.append(v)
        if not vecs:
            return np.zeros((0, 0), dtype=np.float32)
        return np.vstack(vecs)
