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
  GET  /models        -> model availability + paths
  GET  /health        -> {"ok": true}
  GET  /progress      -> current operation progress (poll every 2s)
  GET  /preflight     -> disk space, model status, embedding gaps, warnings

All responses are JSON. Server binds to 127.0.0.1 only — never exposed.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import traceback
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

from .store import Store
from .importers import ALL_IMPORTERS, pick_importer
from .voice import fingerprint, render_voice_directive
from .models import (
    resolve_chat, resolve_embed, status as models_status,
    MODELS, models_dir, disk_free_gb,
)

# Lazy-loaded heavy objects
_store: Store | None = None
_embedder = None
_retriever = None
_chatter = None
_profile = None  # Profile object
_profile_ctx_cache: dict[int, str] = {}  # year -> profile context string
_config: dict = {}

# ── Progress tracking ──────────────────────────────────────────────────
# Polled by the UI every ~2 seconds via GET /progress.
_progress: dict = {
    "operation": None,       # "downloading_model", "embedding", "extracting_profile", "training", etc.
    "detail": "",            # e.g. "Gemma-3-4B-Instruct (2.49 GB)"
    "current": 0,            # items processed so far
    "total": 0,              # total items to process
    "percent": 0,            # 0-100
    "started_at": None,      # ISO-8601 timestamp
}


def _progress_reset():
    """Clear progress after an operation completes."""
    _progress.update(
        operation=None, detail="", current=0, total=0, percent=0,
        started_at=None,
    )


def _progress_start(operation: str, detail: str = "", total: int = 0):
    """Mark the beginning of a tracked operation."""
    _progress.update(
        operation=operation,
        detail=detail,
        current=0,
        total=total,
        percent=0,
        started_at=datetime.now(timezone.utc).isoformat(),
    )


def _progress_update(current: int, total: int | None = None, detail: str | None = None):
    """Update progress counters mid-operation."""
    _progress["current"] = current
    if total is not None:
        _progress["total"] = total
    if detail is not None:
        _progress["detail"] = detail
    t = _progress["total"]
    _progress["percent"] = int(current * 100 / t) if t > 0 else 0


def _download_progress_callback(downloaded_bytes: int, total_bytes: int, desc: str):
    """Callback passed to models.resolve_* to relay download progress."""
    _progress["operation"] = "downloading_model"
    _progress["detail"] = desc
    _progress["current"] = downloaded_bytes
    _progress["total"] = total_bytes
    _progress["percent"] = int(downloaded_bytes * 100 / total_bytes) if total_bytes > 0 else 0
    if _progress["started_at"] is None:
        _progress["started_at"] = datetime.now(timezone.utc).isoformat()


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
    """Build profile context for a given year and query.

    Identity questions ("who am I?", "tell me about yourself") get a rich
    profile (~500 tokens). Normal chat gets a compact version (~200 tokens)
    which is cached per-year.
    """
    profile = _get_profile()
    if profile is None:
        return ""
    from .profile.context import build_profile_context, _is_identity_query

    # Identity questions bypass cache and get the full profile
    if query and _is_identity_query(query):
        return build_profile_context(profile, year, query=query)

    # Normal chat uses cached compact context
    if year not in _profile_ctx_cache:
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
        self.send_header("Access-Control-Expose-Headers", "X-Timeout-Hint")
        self.end_headers()

    def do_GET(self):
        if self.path == "/health":
            _json_response(self, 200, {"ok": True})
        elif self.path == "/stats":
            self._stats()
        elif self.path == "/models":
            _json_response(self, 200, models_status())
        elif self.path == "/progress":
            _json_response(self, 200, dict(_progress))
        elif self.path == "/preflight":
            self._preflight()
        elif self.path == "/logs":
            self._logs()
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
        model_path = body.get("model", "") or resolve_embed(
            progress_callback=_download_progress_callback,
        )
        if not model_path:
            _json_response(self, 400, {"error": "embed model not found"})
            return
        if _embedder is None:
            from .rag import Embedder
            _embedder = Embedder(Path(model_path))

        store = _get_store()

        # Count total messages needing embedding for progress reporting
        total_needed = store.conn.execute(
            "SELECT COUNT(*) FROM messages m "
            "LEFT JOIN embeddings e ON e.message_id = m.id "
            "WHERE e.message_id IS NULL AND m.text <> ''"
        ).fetchone()[0]

        _progress_start("embedding", f"{total_needed} messages", total=total_needed)

        embedded = 0
        for chunk in store.iter_missing_embeddings(batch=128):
            texts = [r["text"] for r in chunk]
            vecs = _embedder.embed(texts)
            store.put_embeddings(list(zip([r["id"] for r in chunk], vecs)))
            embedded += len(chunk)
            _progress_update(embedded)

        _progress_reset()
        _json_response(self, 200, {"embedded": embedded})

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
        model_path = body.get("model", "") or resolve_chat(
            progress_callback=_download_progress_callback,
        )
        if not model_path:
            _json_response(self, 400, {"error": "chat model not found"})
            return
        self_name = _config.get("self_name", "")
        if not self_name:
            _json_response(self, 400, {"error": "run /init first"})
            return

        from .profile.extractor import ProfileExtractor
        import dataclasses

        _progress_start("extracting_profile", "analyzing conversations")

        def _profile_progress(step: str, detail: str = ""):
            """Relay profile extractor progress into global _progress."""
            _progress_update(
                _progress["current"],
                detail=f"{step}: {detail}" if detail else step,
            )

        store = _get_store()
        extractor = ProfileExtractor(Path(model_path))
        profile = extractor.extract(store, self_name, on_progress=_profile_progress)

        # Serialize and save
        profile_data = dataclasses.asdict(profile)
        store.save_profile("full_profile", json.dumps(profile_data))

        # Update cached profile
        _profile = profile
        _profile_ctx_cache = {}

        _progress_reset()
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

        model = body.get("model", "") or resolve_chat(
            progress_callback=_download_progress_callback,
        )
        embed_model = body.get("embed_model", "") or resolve_embed(
            progress_callback=_download_progress_callback,
        )
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

        _progress_reset()  # clear any download progress from model resolution

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
        # Include timeout hint so the Tauri client knows to wait longer
        resp_body = {
            "reply": reply,
            "used_messages": used,
            "timeout_hint_s": 300,
        }
        raw = json.dumps(resp_body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("X-Timeout-Hint", "300")
        self.end_headers()
        self.wfile.write(raw)

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
            _progress_start("training", "extracting training pairs")
            from .finetune import extract_pairs, format_for_gemma, save_jsonl
            from .finetune.format import split_dataset

            max_pairs = body.get("max_pairs", 3000)
            pairs = extract_pairs(store, self_name=self_name, max_pairs=max_pairs)
            if not pairs:
                _progress_reset()
                _json_response(self, 200, {
                    "status": "error",
                    "error": "no training pairs found",
                })
                return

            _progress_update(len(pairs), detail=f"formatting {len(pairs)} pairs")
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
                _progress_reset()
                _json_response(self, 200, result)
                return

        if step in ("train", "full"):
            _progress_start("training", "LoRA fine-tuning in progress")
            from .finetune import train_lora, TrainConfig
            config = TrainConfig(
                model_name=body.get("model_name", "google/gemma-3-4b-it"),
                num_epochs=body.get("epochs", 2),
                lora_rank=body.get("lora_rank", 16),
            )
            train_result = train_lora(config)
            if step == "train":
                _progress_reset()
                _json_response(self, 200, train_result)
                return
            result["train_result"] = train_result

        if step in ("convert", "full"):
            _progress_start("training", "converting adapter to GGUF")
            from .finetune import convert_adapter
            adapter_dir = body.get("adapter_dir", "") or str(
                _data_dir() / "finetune" / "adapter"
            )
            convert_result = convert_adapter(adapter_dir)
            if step == "convert":
                _progress_reset()
                _json_response(self, 200, convert_result)
                return
            result["convert_result"] = convert_result

        _progress_reset()
        _json_response(self, 200, result)

    def _preflight(self):
        """Pre-flight check: disk space, model status, embedding gaps, warnings."""
        warnings: list[str] = []
        data_path = _data_dir()

        # Disk space
        free_gb = disk_free_gb(data_path)

        # Model availability
        model_info = models_status()
        models_needed: list[str] = []
        space_needed_gb = 0.0
        for kind, entry in model_info.items():
            if not entry["available"]:
                models_needed.append(entry["name"])
                space_needed_gb += entry["size_gb"]

        if models_needed and free_gb < space_needed_gb:
            warnings.append(
                f"Only {free_gb:.1f} GB free, need ~{space_needed_gb:.1f} GB "
                f"for model download ({', '.join(models_needed)})"
            )

        # Embedding gap
        total_messages = 0
        messages_needing_embedding = 0
        try:
            store = _get_store()
            total_messages = store.count()
            messages_needing_embedding = store.conn.execute(
                "SELECT COUNT(*) FROM messages m "
                "LEFT JOIN embeddings e ON e.message_id = m.id "
                "WHERE e.message_id IS NULL AND m.text <> ''"
            ).fetchone()[0]
            if messages_needing_embedding > 10000:
                warnings.append(
                    f"{messages_needing_embedding:,} messages need embedding — "
                    f"this may take several minutes"
                )
        except Exception:
            pass  # DB may not exist yet on first launch

        _json_response(self, 200, {
            "disk_free_gb": free_gb,
            "models": model_info,
            "models_needed": models_needed,
            "total_messages": total_messages,
            "messages_needing_embedding": messages_needing_embedding,
            "warnings": warnings,
        })

    def _logs(self):
        """Return log directory path, system info, and recent log lines."""
        from .log import log_file, log_dir
        import platform

        logfile = log_file()
        lines = []
        if logfile.exists():
            try:
                all_lines = logfile.read_text(encoding="utf-8", errors="replace").splitlines()
                lines = all_lines[-200:]  # Last 200 lines
            except OSError:
                lines = ["(could not read log file)"]

        # Also check for Tauri logs in the same directory
        tauri_log = log_dir() / "tauri.log"
        tauri_lines = []
        if tauri_log.exists():
            try:
                all_lines = tauri_log.read_text(encoding="utf-8", errors="replace").splitlines()
                tauri_lines = all_lines[-100:]
            except OSError:
                tauri_lines = ["(could not read tauri log file)"]

        # System info for bug reports
        sysinfo = {
            "os": f"{platform.system()} {platform.release()}",
            "arch": platform.machine(),
            "python": sys.version.split()[0],
            "pratibmb_data": str(_data_dir()),
        }

        # Disk space
        try:
            from .models import disk_free_gb
            sysinfo["disk_free_gb"] = round(disk_free_gb(), 1)
        except Exception:
            pass

        _json_response(self, 200, {
            "log_dir": str(log_dir()),
            "log_file": str(logfile),
            "lines": lines,
            "tauri_lines": tauri_lines,
            "system": sysinfo,
        })

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
    # ── Initialize logging before anything else ────────────────────────
    from .log import setup_logging, redirect_print_to_log, log_dir as _log_dir
    logger = setup_logging("pratibmb.server")
    redirect_print_to_log(logger)
    logger.info("=== Pratibmb server starting ===")
    logger.info("Log directory: %s", _log_dir())
    logger.info("Python %s", sys.version.split()[0])

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 11435
    global _config
    cfg_path = _data_dir() / "config.json"
    if cfg_path.exists():
        _config = json.loads(cfg_path.read_text())

    server = HTTPServer(("127.0.0.1", port), Handler)
    logger.info("Listening on 127.0.0.1:%d", port)
    print(f"[pratibmb-server] listening on 127.0.0.1:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server shutting down (KeyboardInterrupt)")
        print("\n[pratibmb-server] shutting down")
    except Exception:
        logger.exception("Server crashed with unhandled exception")
        raise
    finally:
        if _store:
            _store.close()


if __name__ == "__main__":
    main()
