# Pratibmb Desktop

Tauri shell for Pratibmb. Rust backend, plain HTML/JS frontend (zero build step for v0 — we'll switch to Vite + a real framework once the flows stabilize).

## Architecture

```
┌───────────────────────────────────────────────┐
│  Tauri window (webview)                       │
│   ui/index.html  ←  year slider, chat pane    │
└───────────────────────────────────────────────┘
              ▲              │
              │ tauri cmds   │
              │              ▼
┌───────────────────────────────────────────────┐
│  Rust backend (src-tauri/src/main.rs)         │
│   - spawns `llama-server` as a child process  │
│   - owns the SQLite corpus                    │
│   - streams replies back to the webview       │
└───────────────────────────────────────────────┘
              │
              ▼
         llama-server (llama.cpp binary)
         Gemma-3-4B-Instruct Q4_K_M
```

## Build requirements

- Rust (stable) + `cargo`
- The `tauri-cli` (`cargo install tauri-cli --version "^2"`)
- A prebuilt `llama-server` binary bundled in `resources/`

## Status

v0 scaffold only. Not yet wired to the Python core. The near-term plan is:

1. Ship the Python core as the reference backend (what the CLI uses today).
2. Rewrite the hot path (SQLite + cosine + llama-server control) in Rust for the desktop binary.
3. Keep the Python path around as the "developer SDK" for writing new importers.
