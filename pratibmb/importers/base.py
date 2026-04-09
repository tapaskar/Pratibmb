"""
Importer protocol. Every importer is a callable that yields normalized Messages.

Design rule: importers are stateless and streaming. They should be usable on
exports of any size without loading everything into memory.
"""
from __future__ import annotations
from pathlib import Path
from typing import Iterator, Protocol, runtime_checkable
from ..schema import Message


@runtime_checkable
class Importer(Protocol):
    """Each importer declares its name and a self-identifying detector."""

    name: str  # e.g. "whatsapp_txt"

    def detect(self, path: Path) -> bool:
        """Return True if this importer can handle `path`."""
        ...

    def load(self, path: Path, self_name: str) -> Iterator[Message]:
        """
        Yield normalized Messages from `path`.

        `self_name` is the user's name as it appears in the export, used to
        distinguish "self" from "other" authors. Callers must pass the user's
        own display name exactly as it appears in the source.
        """
        ...


def pick_importer(path: Path, importers: list[Importer]) -> Importer | None:
    for imp in importers:
        try:
            if imp.detect(path):
                return imp
        except Exception:
            continue
    return None
