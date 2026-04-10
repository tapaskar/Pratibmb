"""
Lightweight HTTP server wrapping the Pratibmb core.

Spawned by the Tauri desktop app as a sidecar process. No Flask/FastAPI —
stdlib only so we don't add deps to the shipped binary.

Endpoints:
  POST /init          {"self_name": "YourName"}
  POST /import        {"path": "/path/to/export"}
  POST /embed         {"model": "/path/to/embed.gguf"}
  POST /voice         {}
  POST /profile       {}           -- extract structured profile (one-time)
  POST /chat          {"year": 2022, "prompt": "hey"}
  POST /finetune      {"step": "extract"|"train"|"convert"|"full"}
  GET  /stats         -> corpus summary
  GET  /health        -> {"ok": true}

All responses are JSON. Server binds to 127.0.0.1 only — never exposed.
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

from .store import Store
from .importers import ALL_IMPORTERS, pick_importer
from .voice import fingerprint, render_voice_directive


def _env_model(env_key: str, default_name: str) -> str:
    """Resolve a model path from env var, or look in common locations.

    For the chat model, also checks for a fine-tuned model first.
    """
    v = os.environ.get(env_key, "")
    if v and Path(v).exists():
        return v
    search_dirs = [
        Path.home() / ".pratibmb" / "models",
        Path.home() / "models",
        Path.cwd() / "models",
    ]
    # Prefer fine-tuned model over base model for chat
    if env_key == "PRATIBMB_CHAT_MODEL":
        finetuned_name = "pratibmb-gemma-3-4b-finetuned-q4_k_m.gguf"
        for d in search_dirs:
            p = d / finetuned_name
            if p.exists():
                print(f"[server] using fine-tuned model: {p}", flush=True)
                return str(p)
    for d in search_dirs:
        p = d / default_name
        if p.exists():
            return str(p)
    return ""

# Lazy-loaded heavy objects
_store: Store | None = None
_embedder = None
_retriever = None
_chatter = None
_profile = None  # Profile object
_profile_ctx_cache: dict[int, str] = {}  # year -> profile context string
_config: dict = {}


def _data_dir() -> Path:
    return Path.home() / ".pratibmb"


def _db_path() -> Path:
    return _data_dir() / "corpus.db"


def _get_store() -> Store:
    global _store
    if _store is None:
        _data_dir().mkdir(parents=True, exist_ok=True)
        _store = Store(_db_path())
    return _store


def _get_profile():
    """Load profile from DB if available."""
    global _profile
    if _profile is not None:
        return _profile
    store = _get_store()
    raw = store.load_profile("full_profile")
    if raw:
        from .profile.schema import (
            Profile, Relationship, LifeEvent,
            Interest, YearSummary, ThreadSummary,
        )
        data = json.loads(raw)
        p = Profile(self_name=data.get("self_name", ""))
        for r in data.get("relationships", []):
            p.relationships.append(Relationship(**r))
        for e in data.get("life_events", []):
            p.life_events.append(LifeEvent(**e))
        for i in data.get("interests", []):
            p.interests.append(Interest(**i))
        for ys in data.get("year_summaries", []):
            p.year_summaries.append(YearSummary(**ys))
        for ts in data.get("thread_summaries", []):
            p.thread_summaries.append(ThreadSummary(**ts))
        p.communication_style = data.get("communication_style", {})
        _profile = p
    return _profile


def _get_profile_context(year: int, query: str = "") -> str:
    """Build profile context for a given year, with caching."""
    profile = _get_profile()
    if profile is None:
        return ""
    # Cache key includes year (query-specific parts are cheap to add)
    if year not in _profile_ctx_cache:
        from .profile.context import build_profile_context
        _profile_ctx_cache[year] = build_profile_context(profile, year)
    base = _profile_ctx_cache[year]
    # Add query-specific relationship info
    if query and profile:
        query_lower = query.lower()
        for r in profile.relationships:
            if r.person_name.lower() in query_lower and r.summary:
                base += f"\nAbout {r.person_name}: {r.summary}"
                break
    return base


def _json_response(handler: BaseHTTPRequestHandler, code: int, body: Any):
    raw = json.dumps(body).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(raw)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(raw)


def _read_body(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", 0))
    if length == 0:
        return {}
    return json.loads(handler.rfile.read(length))


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[server] {fmt % args}", flush=True)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            _json_response(self, 200, {"ok": True})
        elif self.path == "/stats":
            self._stats()
        else:
            _json_response(self, 404, {"error": "not found"})

    def do_POST(self):
        try:
            body = _read_body(self)
            if self.path == "/init":
                self._init(body)
            elif self.path == "/import":
                self._import(body)
            elif self.path == "/embed":
                self._embed(body)
            elif self.path == "/voice":
                self._voice(body)
            elif self.path == "/profile":
                self._extract_profile(body)
            elif self.path == "/chat":
                self._chat(body)
            elif self.path == "/finetune":
                self._finetune(body)
            else:
                _json_response(self, 404, {"error": "not found"})
        except Exception as e:
            traceback.print_exc()
            _json_response(self, 500, {"error": str(e)})

    def _init(self, body: dict):
        global _config
        name = body.get("self_name", "")
        if not name:
            _json_response(self, 400, {"error": "self_name required"})
            return
        _config["self_name"] = name
        cfg_path = _data_dir() / "config.json"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(json.dumps(_config, indent=2))
        _get_store()
        _json_response(self, 200, {"ok": True, "data_dir": str(_data_dir())})

    def _import(self, body: dict):
        path = Path(body.get("path", ""))
        if not path.exists():
            _json_response(self, 400, {"error": f"path not found: {path}"})
            return
        self_name = _config.get("self_name", "")
        if not self_name:
            _json_response(self, 400, {"error": "run /init first"})
            return
        imp = pick_importer(path, ALL_IMPORTERS)
        if imp is None:
            _json_response(self, 400, {"error": f"no importer for {path}"})
            return
        store = _get_store()
        count = 0
        buf = []
        for msg in imp.load(path, self_name):
            buf.append(msg)
            if len(buf) >= 500:
                store.add_messages(buf)
                count += len(buf)
                buf = []
        if buf:
            store.add_messages(buf)
            count += len(buf)
        _json_response(self, 200, {"imported": count, "source": imp.name})

    def _embed(self, body: dict):
        global _embedder
        model_path = body.get("model", "") or _env_model(
            "PRATIBMB_EMBED_MODEL", "nomic-embed-text-v1.5-q4_k_m.gguf")
        if not model_path:
            _json_response(self, 400, {"error": "embed model not found"})
            return
        if _embedder is None:
            from .rag import Embedder
            _embedder = Embedder(Path(model_path))
        store = _get_store()
        total = 0
        for chunk in store.iter_missing_embeddings(batch=128):
            texts = [r["text"] for r in chunk]
            vecs = _embedder.embed(texts)
            store.put_embeddings(list(zip([r["id"] for r in chunk], vecs)))
            total += len(chunk)
        _json_response(self, 200, {"embedded": total})

    def _voice(self, body: dict):
        store = _get_store()
        fp = fingerprint(store)
        vd = render_voice_directive(fp)
        voice_path = _data_dir() / "voice.json"
        voice_path.write_text(json.dumps(fp, indent=2))
        _json_response(self, 200, {"fingerprint": fp, "directive": vd})

    def _extract_profile(self, body: dict):
        """Run the profile extraction pipeline."""
        global _profile, _profile_ctx_cache
        model_path = body.get("model", "") or _env_model(
            "PRATIBMB_CHAT_MODEL", "gemma-3-4b-it-q4_k_m.gguf")
        if not model_path:
            _json_response(self, 400, {"error": "chat model not found"})
            return
        self_name = _config.get("self_name", "")
        if not self_name:
            _json_response(self, 400, {"error": "run /init first"})
            return

        from .profile.extractor import ProfileExtractor
        import dataclasses

        store = _get_store()
        extractor = ProfileExtractor(Path(model_path))
        profile = extractor.extract(store, self_name)

        # Serialize and save
        profile_data = dataclasses.asdict(profile)
        store.save_profile("full_profile", json.dumps(profile_data))

        # Update cached profile
        _profile = profile
        _profile_ctx_cache = {}

        _json_response(self, 200, {
            "ok": True,
            "relationships": len(profile.relationships),
            "life_events": len(profile.life_events),
            "year_summaries": len(profile.year_summaries),
        })

    def _chat(self, body: dict):
        global _chatter, _retriever, _embedder
        year = body.get("year")
        prompt = body.get("prompt", "")
        if not year or not prompt:
            _json_response(self, 400, {"error": "year and prompt required"})
            return

        model = body.get("model", "") or _env_model(
            "PRATIBMB_CHAT_MODEL", "gemma-3-4b-it-q4_k_m.gguf")
        embed_model = body.get("embed_model", "") or _env_model(
            "PRATIBMB_EMBED_MODEL", "nomic-embed-text-v1.5-q4_k_m.gguf")
        chat_format = body.get("chat_format", "gemma")

        if _embedder is None:
            if not embed_model:
                _json_response(self, 400, {"error": "embed model not found. Set PRATIBMB_EMBED_MODEL env var or place model in ~/.pratibmb/models/"})
                return
            from .rag import Embedder
            _embedder = Embedder(Path(embed_model))

        if _retriever is None:
            from .rag import Retriever
            _retriever = Retriever(_get_store(), _embedder)

        if _chatter is None:
            if not model:
                _json_response(self, 400, {"error": "chat model not found. Set PRATIBMB_CHAT_MODEL env var or place model in ~/.pratibmb/models/"})
                return
            from .llm import Chatter
            _chatter = Chatter(Path(model), chat_format=chat_format)

        from .rag import format_context

        # Retrieve with thread context
        hits = _retriever.retrieve(prompt, year_max=int(year), top_k=6,
                                   thread_window=3)
        ctx = format_context(hits)

        # Build profile context for this year
        profile_ctx = _get_profile_context(int(year), query=prompt)
        self_name = _config.get("self_name", "you")

        reply = _chatter.reply(
            year=int(year),
            context_block=ctx,
            user_prompt=prompt,
            profile_context=profile_ctx,
            self_name=self_name,
        )
        used = [{"text": h["text"][:100], "year": h["year"],
                 "thread": h["thread_name"], "score": round(h["score"], 3)}
                for h in hits]
        _json_response(self, 200, {"reply": reply, "used_messages": used})

    def _finetune(self, body: dict):
        """Run the fine-tuning pipeline (extract, optionally train+convert).

        Body params:
          step: "extract" | "train" | "convert" | "full" (default: "extract")
          self_name: override self_name from config
          max_pairs: max training pairs (default 3000)
          model_name: HuggingFace model for training
          epochs: number of training epochs
          lora_rank: LoRA rank
        """
        step = body.get("step", "extract")
        self_name = body.get("self_name", "") or _config.get("self_name", "")
        if not self_name:
            _json_response(self, 400, {"error": "self_name required (run /init first)"})
            return

        store = _get_store()

        if step in ("extract", "full"):
            from .finetune import extract_pairs, format_for_gemma, save_jsonl
            from .finetune.format import split_dataset

            max_pairs = body.get("max_pairs", 3000)
            pairs = extract_pairs(store, self_name=self_name, max_pairs=max_pairs)
            if not pairs:
                _json_response(self, 200, {
                    "status": "error",
                    "error": "no training pairs found",
                })
                return

            records = format_for_gemma(pairs)
            train_recs, val_recs = split_dataset(records, train_ratio=0.9)

            data_dir = _data_dir() / "finetune" / "data"
            n_train = save_jsonl(train_recs, data_dir / "train.jsonl")
            n_val = save_jsonl(val_recs, data_dir / "valid.jsonl")

            result = {
                "status": "ok",
                "step": "extract",
                "pairs": len(pairs),
                "train": n_train,
                "val": n_val,
                "data_dir": str(data_dir),
            }

            if step == "extract":
                _json_response(self, 200, result)
                return

        if step in ("train", "full"):
            from .finetune import train_lora, TrainConfig
            config = TrainConfig(
                model_name=body.get("model_name", "google/gemma-3-4b-it"),
                num_epochs=body.get("epochs", 2),
                lora_rank=body.get("lora_rank", 16),
            )
            train_result = train_lora(config)
            if step == "train":
                _json_response(self, 200, train_result)
                return
            result["train_result"] = train_result

        if step in ("convert", "full"):
            from .finetune import convert_adapter
            adapter_dir = body.get("adapter_dir", "") or str(
                _data_dir() / "finetune" / "adapter"
            )
            convert_result = convert_adapter(adapter_dir)
            if step == "convert":
                _json_response(self, 200, convert_result)
                return
            result["convert_result"] = convert_result

        _json_response(self, 200, result)

    def _stats(self):
        store = _get_store()
        total = store.count()
        self_total = store.count(author="self")
        has_profile = store.load_profile("full_profile") is not None
        _json_response(self, 200, {
            "total": total,
            "self_total": self_total,
            "has_profile": has_profile,
        })


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 11435
    global _config
    cfg_path = _data_dir() / "config.json"
    if cfg_path.exists():
        _config = json.loads(cfg_path.read_text())

    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"[pratibmb-server] listening on 127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[pratibmb-server] shutting down")
    finally:
        if _store:
            _store.close()


if __name__ == "__main__":
    main()
