// Pratibmb desktop backend (Tauri 2.x).
//
// Spawns the Pratibmb Python HTTP server as a sidecar on 127.0.0.1:11435,
// then proxies commands from the webview to it via reqwest.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::process::{Child, Command};
use std::sync::Mutex;
use tauri::State;

const SERVER_URL: &str = "http://127.0.0.1:11435";

struct ServerProcess(Mutex<Option<Child>>);

#[derive(Serialize, Deserialize)]
struct ChatArgs {
    year: u32,
    prompt: String,
    #[serde(default)]
    model: String,
    #[serde(default)]
    embed_model: String,
    #[serde(default)]
    chat_format: String,
}

#[derive(Serialize, Deserialize)]
struct ChatResult {
    reply: String,
    used_messages: Vec<serde_json::Value>,
}

#[derive(Serialize, Deserialize)]
struct InitArgs {
    self_name: String,
}

#[derive(Serialize, Deserialize)]
struct ImportArgs {
    path: String,
}

#[derive(Serialize, Deserialize)]
struct EmbedArgs {
    model: String,
}

// Generic proxy: POST JSON to the Python server
async fn post_json(path: &str, body: &impl Serialize) -> Result<serde_json::Value, String> {
    let url = format!("{}{}", SERVER_URL, path);
    let client = reqwest::Client::new();
    let resp = client
        .post(&url)
        .json(body)
        .timeout(std::time::Duration::from_secs(120))
        .send()
        .await
        .map_err(|e| format!("server request failed: {}", e))?;
    let status = resp.status();
    let body_text = resp.text().await.map_err(|e| format!("read error: {}", e))?;
    if !status.is_success() {
        return Err(format!("server returned {}: {}", status, body_text));
    }
    serde_json::from_str(&body_text).map_err(|e| format!("json parse error: {}", e))
}

async fn get_json(path: &str) -> Result<serde_json::Value, String> {
    let url = format!("{}{}", SERVER_URL, path);
    let resp = reqwest::get(&url)
        .await
        .map_err(|e| format!("server request failed: {}", e))?;
    let body = resp.text().await.map_err(|e| format!("read error: {}", e))?;
    serde_json::from_str(&body).map_err(|e| format!("json parse error: {}", e))
}

#[tauri::command]
async fn init_user(args: InitArgs) -> Result<serde_json::Value, String> {
    post_json("/init", &args).await
}

#[tauri::command]
async fn import_file(args: ImportArgs) -> Result<serde_json::Value, String> {
    post_json("/import", &args).await
}

#[tauri::command]
async fn embed(args: EmbedArgs) -> Result<serde_json::Value, String> {
    post_json("/embed", &args).await
}

#[tauri::command]
async fn voice() -> Result<serde_json::Value, String> {
    post_json("/voice", &serde_json::json!({})).await
}

#[tauri::command]
async fn chat_turn(args: ChatArgs) -> Result<serde_json::Value, String> {
    post_json("/chat", &args).await
}

#[tauri::command]
async fn stats() -> Result<serde_json::Value, String> {
    get_json("/stats").await
}

#[tauri::command]
async fn health() -> Result<serde_json::Value, String> {
    get_json("/health").await
}

fn spawn_python_server() -> Option<Child> {
    // Try to find python in common locations
    let pythons = [
        // User's llm-eval venv (known to have all deps)
        format!("{}/llm-eval/.venv/bin/python", std::env::var("HOME").unwrap_or_default()),
        "python3".to_string(),
        "python".to_string(),
    ];

    for py in &pythons {
        match Command::new(py)
            .args(["-m", "pratibmb.server", "11435"])
            .env("PYTHONPATH", get_pythonpath())
            .spawn()
        {
            Ok(child) => {
                eprintln!("[tauri] spawned python server (pid {})", child.id());
                return Some(child);
            }
            Err(e) => {
                eprintln!("[tauri] failed to spawn with {}: {}", py, e);
            }
        }
    }
    eprintln!("[tauri] WARNING: could not spawn python server");
    None
}

fn get_pythonpath() -> String {
    // Add the Pratibmb package root to PYTHONPATH
    let exe = std::env::current_exe().unwrap_or_default();
    let mut dir = exe.parent().unwrap_or(std::path::Path::new(".")).to_path_buf();
    // In dev: exe is in target/release or target/debug
    // Walk up to find the repo root containing pratibmb/
    for _ in 0..6 {
        if dir.join("pratibmb").is_dir() {
            return dir.to_string_lossy().to_string();
        }
        if let Some(parent) = dir.parent() {
            dir = parent.to_path_buf();
        } else {
            break;
        }
    }
    // Fallback: the known path on this machine
    "/Volumes/wininstall/Pratibmb".to_string()
}

fn main() {
    let child = spawn_python_server();

    // Give the server a moment to start
    std::thread::sleep(std::time::Duration::from_millis(1500));

    tauri::Builder::default()
        .manage(ServerProcess(Mutex::new(child)))
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            init_user, import_file, embed, voice, chat_turn, stats, health
        ])
        .on_window_event(|_window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                // Server process will be killed when ServerProcess is dropped
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running pratibmb");
}

impl Drop for ServerProcess {
    fn drop(&mut self) {
        if let Ok(mut guard) = self.0.lock() {
            if let Some(ref mut child) = *guard {
                eprintln!("[tauri] killing python server (pid {})", child.id());
                let _ = child.kill();
                let _ = child.wait();
            }
        }
    }
}
