// Pratibmb desktop backend (Tauri 2.x).
//
// v0 responsibilities:
//   - Spawn a llama.cpp `llama-server` as a child process bound to 127.0.0.1.
//   - Expose `chat_turn`, `import_file`, `stats` commands to the webview.
//   - Talk to llama-server over HTTP using `reqwest`.
//
// This file deliberately keeps the surface tiny. The real work lives in the
// Python core today; we will port the SQLite + retrieval path to Rust later.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};

#[derive(Serialize, Deserialize)]
struct ChatTurnArgs {
    year: u32,
    prompt: String,
}

#[derive(Serialize, Deserialize)]
struct ChatTurnResult {
    reply: String,
    used_messages: Vec<String>,
}

#[tauri::command]
async fn chat_turn(args: ChatTurnArgs) -> Result<ChatTurnResult, String> {
    // TODO: wire into the Python core (or the Rust port) for real retrieval.
    // For now we return a placeholder so the UI can be developed independently.
    Ok(ChatTurnResult {
        reply: format!(
            "(stub) past-you ({}) heard: {}",
            args.year, args.prompt
        ),
        used_messages: vec![],
    })
}

#[tauri::command]
async fn import_file(_path: String) -> Result<u64, String> {
    // TODO: call into the Python importer layer via a bundled sidecar.
    Ok(0)
}

#[derive(Serialize)]
struct Stats {
    total: u64,
    self_total: u64,
    oldest_year: Option<u32>,
    newest_year: Option<u32>,
}

#[tauri::command]
async fn stats() -> Result<Stats, String> {
    Ok(Stats {
        total: 0,
        self_total: 0,
        oldest_year: None,
        newest_year: None,
    })
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![chat_turn, import_file, stats])
        .run(tauri::generate_context!())
        .expect("error while running pratibmb");
}
