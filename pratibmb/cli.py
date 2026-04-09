"""
Pratibmb CLI.

Commands:
  pratibmb init                        — create data dir, set user name
  pratibmb import <path>               — ingest an export file or directory
  pratibmb embed                       — embed any messages lacking vectors
  pratibmb voice                       — fingerprint self-voice and cache it
  pratibmb chat --year YYYY            — interactive REPL with past-you
  pratibmb stats                       — corpus summary
"""
from __future__ import annotations
import json
import sys
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

from .importers import ALL_IMPORTERS, pick_importer
from .store import Store
from .voice import fingerprint, render_voice_directive, save as save_voice

console = Console()


def data_dir() -> Path:
    return Path.home() / ".pratibmb"


def db_path() -> Path:
    return data_dir() / "corpus.db"


def config_path() -> Path:
    return data_dir() / "config.json"


def voice_path() -> Path:
    return data_dir() / "voice.json"


def load_config() -> dict:
    p = config_path()
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def save_config(cfg: dict) -> None:
    config_path().parent.mkdir(parents=True, exist_ok=True)
    config_path().write_text(json.dumps(cfg, indent=2))


@click.group()
def main() -> None:
    """Pratibmb — chat with your 10-years-younger self. 100% local."""


@main.command()
@click.option("--name", prompt="Your name as it appears in your chat exports",
              help="The exact display name you use in WhatsApp/Facebook exports.")
def init(name: str) -> None:
    """Create ~/.pratibmb and remember your display name."""
    data_dir().mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    cfg["self_name"] = name
    save_config(cfg)
    Store(db_path()).close()
    console.print(f"[green]ready.[/green] data lives at {data_dir()}")


@main.command("import")
@click.argument("path", type=click.Path(exists=True, path_type=Path))
def import_cmd(path: Path) -> None:
    """Ingest a WhatsApp .txt, a Facebook DYI folder, an Instagram DYI folder,
    or a single message_*.json."""
    cfg = load_config()
    if "self_name" not in cfg:
        console.print("[red]run `pratibmb init` first[/red]")
        sys.exit(1)
    self_name = cfg["self_name"]

    importer = pick_importer(path, ALL_IMPORTERS)
    if importer is None:
        console.print(f"[red]no importer could handle[/red] {path}")
        sys.exit(2)
    console.print(f"[cyan]using[/cyan] {importer.name}  →  {path}")

    store = Store(db_path())
    try:
        count = 0
        buf = []
        for msg in importer.load(path, self_name):
            buf.append(msg)
            if len(buf) >= 500:
                store.add_messages(buf)
                count += len(buf)
                buf = []
                console.print(f"  [dim]imported {count}...[/dim]")
        if buf:
            store.add_messages(buf)
            count += len(buf)
        console.print(f"[green]{count} messages imported[/green]")
    finally:
        store.close()


@main.command()
@click.option("--model", type=click.Path(exists=True, path_type=Path),
              required=True, help="Path to a GGUF embedding model.")
@click.option("--batch", default=64, help="Embedding batch size.")
def embed(model: Path, batch: int) -> None:
    """Embed any messages that don't yet have vectors."""
    from .rag import Embedder
    store = Store(db_path())
    try:
        embedder = Embedder(model)
        total = 0
        for chunk in store.iter_missing_embeddings(batch=batch):
            texts = [r["text"] for r in chunk]
            vecs = embedder.embed(texts)
            store.put_embeddings(list(zip([r["id"] for r in chunk], vecs)))
            total += len(chunk)
            console.print(f"  [dim]embedded {total}...[/dim]")
        console.print(f"[green]{total} new embeddings[/green]")
    finally:
        store.close()


@main.command()
@click.option("--year-max", type=int, default=None,
              help="Only look at messages up to this year.")
def voice(year_max: int | None) -> None:
    """Fingerprint your own writing voice."""
    store = Store(db_path())
    try:
        fp = fingerprint(store, year_max=year_max)
        save_voice(fp, voice_path())
        console.print(json.dumps(fp, indent=2))
        directive = render_voice_directive(fp)
        if directive:
            console.print(f"\n[cyan]style directive:[/cyan] {directive}")
    finally:
        store.close()


@main.command()
@click.option("--model", type=click.Path(exists=True, path_type=Path),
              required=True, help="Path to a GGUF chat model (Gemma-3-4B recommended).")
@click.option("--embed-model", type=click.Path(exists=True, path_type=Path),
              required=True, help="Path to a GGUF embedding model.")
@click.option("--year", type=int, required=True, help="Which version of past-you to talk to.")
@click.option("--chat-format", default="gemma")
def chat(model: Path, embed_model: Path, year: int, chat_format: str) -> None:
    """Interactive REPL with your past self."""
    from .rag import Embedder, Retriever, format_context
    from .llm import Chatter

    store = Store(db_path())
    cfg = load_config()
    if store.count(year_max=year, author="self") == 0:
        console.print(f"[red]no self-messages from year <= {year}[/red]")
        store.close()
        sys.exit(3)

    voice_fp = {}
    if voice_path().exists():
        voice_fp = json.loads(voice_path().read_text())
    directive = render_voice_directive(voice_fp)

    console.print(f"[cyan]loading embedder...[/cyan]")
    embedder = Embedder(embed_model)
    retriever = Retriever(store, embedder)

    console.print(f"[cyan]loading chat model...[/cyan]")
    chatter = Chatter(model, chat_format=chat_format)

    console.rule(f"[bold]chatting with {cfg.get('self_name','you')} in {year}[/bold]")
    console.print("[dim]type 'exit' to quit[/dim]\n")

    try:
        while True:
            try:
                user = Prompt.ask("[bold green]you[/bold green]").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not user or user.lower() in {"exit", "quit", ":q"}:
                break
            hits = retriever.retrieve(user, year_max=year, top_k=8)
            ctx = format_context(hits)
            reply = chatter.reply(year=year, voice_directive=directive,
                                  context_block=ctx, user_prompt=user)
            console.print(f"[bold magenta]past-you[/bold magenta]: {reply}\n")
    finally:
        store.close()


@main.command()
def stats() -> None:
    """Corpus summary."""
    store = Store(db_path())
    try:
        total = store.count()
        self_total = store.count(author="self")
        table = Table(title="Pratibmb corpus")
        table.add_column("metric")
        table.add_column("value", justify="right")
        table.add_row("total messages", str(total))
        table.add_row("your messages", str(self_total))
        for year in range(2008, datetime.now().year + 1):
            c = store.count(year_max=year) - store.count(year_max=year - 1)
            if c:
                table.add_row(f"  {year}", str(c))
        console.print(table)
    finally:
        store.close()


if __name__ == "__main__":
    main()
