"""
Lightweight HTTP server wrapping the Pratibmb core.

Spawned by the Tauri desktop app as a sidecar process. No Flask/FastAPI —
stdlib only so we don't add deps to the shipped binary.

Endpoints:
  POST /init          {"self_name": "YourName"}
  POST /import        {"path": "/path/to/export"}
  POST /embed         {"model": "/path/to/embed.gguf"}
  POST /voice         {}
  POST /chat          {"year": 2022, "prompt": "hey"}
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
    """Resolve a model path from env var, or look in common locations."""
    v = os.environ.get(env_key, "")
    if v and Path(v).exists():
        return v
    # Search common locations
    for d in [
        Path.home() / ".pratibmb" / "models",
        Path.home() / "models",
        Path.cwd() / "models",
    ]:
        p = d / default_name
        if p.exists():
            return str(p)
    return ""

# Lazy-loaded heavy objects
_store: Store | None = None
_embedder = None
_retriever = None
_chatter = None
_voice_directive: str = ""
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
            elif self.path == "/chat":
                self._chat(body)
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
        model_path = body.get("model", "")
        if not model_path:
            _json_response(self, 400, {"error": "model path required"})
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
        global _voice_directive
        store = _get_store()
        fp = fingerprint(store)
        _voice_directive = render_voice_directive(fp)
        voice_path = _data_dir() / "voice.json"
        voice_path.write_text(json.dumps(fp, indent=2))
        _json_response(self, 200, {"fingerprint": fp, "directive": _voice_directive})

    def _chat(self, body: dict):
        global _chatter, _retriever, _embedder, _voice_directive
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
        hits = _retriever.retrieve(prompt, year_max=int(year), top_k=8)
        ctx = format_context(hits)
        reply = _chatter.reply(
            year=int(year),
            voice_directive=_voice_directive,
            context_block=ctx,
            user_prompt=prompt,
        )
        used = [{"text": h["text"][:100], "year": h["year"],
                 "thread": h["thread_name"], "score": round(h["score"], 3)}
                for h in hits]
        _json_response(self, 200, {"reply": reply, "used_messages": used})

    def _stats(self):
        store = _get_store()
        total = store.count()
        self_total = store.count(author="self")
        _json_response(self, 200, {
            "total": total,
            "self_total": self_total,
        })


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 11435
    # Load existing config if present
    global _config
    cfg_path = _data_dir() / "config.json"
    if cfg_path.exists():
        _config = json.loads(cfg_path.read_text())
    # Load existing voice directive
    global _voice_directive
    vp = _data_dir() / "voice.json"
    if vp.exists():
        import importlib
        fp = json.loads(vp.read_text())
        _voice_directive = render_voice_directive(fp)

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
