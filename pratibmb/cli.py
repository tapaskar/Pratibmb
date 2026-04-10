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


@main.group()
def finetune() -> None:
    """LoRA fine-tuning pipeline."""


@finetune.command("extract-pairs")
@click.option("--db", type=click.Path(path_type=Path), default=None,
              help="Path to corpus DB. Defaults to ~/.pratibmb/corpus.db.")
@click.option("--max-pairs", type=int, default=3000,
              help="Maximum number of training pairs.")
@click.option("--output", type=click.Path(path_type=Path), default=None,
              help="Output directory for JSONL files.")
def finetune_extract(db: Path | None, max_pairs: int, output: Path | None) -> None:
    """Extract training pairs and format as JSONL."""
    from .finetune import extract_pairs, format_for_gemma, save_jsonl
    from .finetune.format import split_dataset
    import os

    cfg = load_config()
    self_name = cfg.get("self_name", "")
    if not self_name:
        console.print("[red]run `pratibmb init` first[/red]")
        sys.exit(1)

    db_file = db or db_path()
    if not db_file.exists():
        console.print(f"[red]database not found: {db_file}[/red]")
        sys.exit(1)

    store = Store(db_file)
    try:
        console.print("[cyan]extracting training pairs...[/cyan]")
        pairs = extract_pairs(store, self_name=self_name, max_pairs=max_pairs)
        console.print(f"[green]extracted {len(pairs)} training pairs[/green]")

        if not pairs:
            console.print("[red]no training pairs found[/red]")
            sys.exit(1)

        console.print("[cyan]formatting for Gemma...[/cyan]")
        records = format_for_gemma(pairs)

        # Split into train/val
        train_recs, val_recs = split_dataset(records, train_ratio=0.9)

        # Determine output directory
        env_dir = os.environ.get("PRATIBMB_DATA_DIR", "")
        base = Path(env_dir) if env_dir else data_dir()
        out = output or (base / "finetune" / "data")

        n_train = save_jsonl(train_recs, out / "train.jsonl")
        n_val = save_jsonl(val_recs, out / "valid.jsonl")

        console.print(f"[green]saved {n_train} train + {n_val} val records to {out}[/green]")

        # Show a few examples
        for i, r in enumerate(records[:2]):
            console.print(f"\n[dim]--- example {i+1} ---[/dim]")
            console.print(r["text"][:300])
    finally:
        store.close()


@finetune.command("train")
@click.option("--model", default="google/gemma-3-4b-it",
              help="HuggingFace model name.")
@click.option("--epochs", type=int, default=2)
@click.option("--lr", type=float, default=1e-4, help="Learning rate.")
@click.option("--rank", type=int, default=16, help="LoRA rank.")
def finetune_train(model: str, epochs: int, lr: float, rank: int) -> None:
    """Run LoRA training via MLX-LM."""
    from .finetune import train_lora, TrainConfig

    config = TrainConfig(
        model_name=model,
        num_epochs=epochs,
        learning_rate=lr,
        lora_rank=rank,
    )
    console.print(f"[cyan]starting LoRA training (rank={rank}, epochs={epochs})...[/cyan]")
    result = train_lora(config)

    if result["status"] == "ok":
        console.print(f"[green]training complete![/green]")
        console.print(f"  adapter: {result['adapter_path']}")
    elif result["status"] == "manual":
        console.print("[yellow]mlx-lm not available. Manual instructions:[/yellow]")
        console.print(result["instructions"])
    else:
        console.print(f"[red]training failed: {result.get('error', 'unknown')}[/red]")
        sys.exit(1)


@finetune.command("convert")
@click.option("--adapter-dir", type=click.Path(path_type=Path), default=None,
              help="Path to MLX adapter directory.")
@click.option("--output", type=click.Path(path_type=Path), default=None,
              help="Output GGUF path.")
@click.option("--base-model", default="google/gemma-3-4b-it",
              help="Base model name for conversion.")
def finetune_convert(adapter_dir: Path | None, output: Path | None,
                     base_model: str) -> None:
    """Convert MLX adapter to GGUF format."""
    from .finetune import convert_adapter
    import os

    if adapter_dir is None:
        env_dir = os.environ.get("PRATIBMB_DATA_DIR", "")
        base = Path(env_dir) if env_dir else data_dir()
        adapter_dir = base / "finetune" / "adapter"

    console.print(f"[cyan]converting adapter from {adapter_dir}...[/cyan]")
    result = convert_adapter(adapter_dir, output_path=output, base_model=base_model)

    if result["status"] == "ok":
        console.print(f"[green]converted! GGUF adapter: {result['output_path']}[/green]")
    elif result["status"] == "manual":
        console.print("[yellow]automatic conversion unavailable. Instructions:[/yellow]")
        console.print(result["instructions"])
    else:
        console.print(f"[red]conversion failed: {result.get('error', 'unknown')}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
