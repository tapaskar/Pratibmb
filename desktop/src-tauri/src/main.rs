// Pratibmb desktop backend (Tauri 2.x).
//
// Spawns the Pratibmb Python HTTP server as a sidecar on 127.0.0.1:11435,
// then proxies commands from the webview to it via reqwest.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use serde::{Deserialize, Serialize};
use std::process::{Child, Command};
use std::sync::Mutex;
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

#[derive(Serialize, Deserialize)]
struct ProfileArgs {
    #[serde(default)]
    model: String,
}

#[derive(Serialize, Deserialize)]
struct FinetuneArgs {
    #[serde(default = "default_finetune_step")]
    step: String,
    #[serde(default)]
    max_pairs: Option<u32>,
    #[serde(default)]
    model_name: String,
    #[serde(default)]
    epochs: Option<u32>,
    #[serde(default)]
    lora_rank: Option<u32>,
}

fn default_finetune_step() -> String {
    "extract".to_string()
}

// Generic proxy: POST JSON to the Python server
async fn post_json(path: &str, body: &impl Serialize) -> Result<serde_json::Value, String> {
    post_json_timeout(path, body, 120).await
}

// POST with custom timeout (seconds) for long-running operations
async fn post_json_timeout(
    path: &str,
    body: &impl Serialize,
    timeout_secs: u64,
) -> Result<serde_json::Value, String> {
    let url = format!("{}{}", SERVER_URL, path);
    let client = reqwest::Client::new();
    let resp = client
        .post(&url)
        .json(body)
        .timeout(std::time::Duration::from_secs(timeout_secs))
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
async fn extract_profile(args: ProfileArgs) -> Result<serde_json::Value, String> {
    // Profile extraction is LLM-heavy — can take 5-10 minutes
    post_json_timeout("/profile", &args, 900).await
}

#[tauri::command]
async fn finetune(args: FinetuneArgs) -> Result<serde_json::Value, String> {
    // Fine-tuning can take 30+ minutes for the full pipeline
    let timeout = match args.step.as_str() {
        "extract" => 120,
        "train" => 3600,
        "convert" => 300,
        "full" => 7200,
        _ => 120,
    };
    post_json_timeout("/finetune", &args, timeout).await
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

    let pythonpath = get_pythonpath();
    eprintln!("[tauri] PYTHONPATH = {}", pythonpath);

    for py in &pythons {
        eprintln!("[tauri] trying: {} -m pratibmb.server 11435", py);
        match Command::new(py)
            .args(["-m", "pratibmb.server", "11435"])
            .env("PYTHONPATH", &pythonpath)
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
    // Check env var first (user override)
    if let Ok(v) = std::env::var("PRATIBMB_ROOT") {
        if std::path::Path::new(&v).join("pratibmb").is_dir() {
            eprintln!("[tauri] PYTHONPATH from PRATIBMB_ROOT: {}", v);
            return v;
        }
    }

    // Walk up from the executable to find the repo root
    let exe = std::env::current_exe().unwrap_or_default();
    let mut dir = exe.parent().unwrap_or(std::path::Path::new(".")).to_path_buf();
    for _ in 0..10 {
        if dir.join("pratibmb").is_dir() {
            eprintln!("[tauri] PYTHONPATH from exe walk: {}", dir.display());
            return dir.to_string_lossy().to_string();
        }
        if let Some(parent) = dir.parent() {
            dir = parent.to_path_buf();
        } else {
            break;
        }
    }

    // Check current working directory
    if let Ok(cwd) = std::env::current_dir() {
        if cwd.join("pratibmb").is_dir() {
            eprintln!("[tauri] PYTHONPATH from cwd: {}", cwd.display());
            return cwd.to_string_lossy().to_string();
        }
    }

    // Common dev locations
    let home = std::env::var("HOME").unwrap_or_default();
    let candidates = [
        format!("{}/Pratibmb", home),
        "/Volumes/wininstall/Pratibmb".to_string(),
    ];
    for c in &candidates {
        let p = std::path::Path::new(c);
        if p.join("pratibmb").is_dir() {
            eprintln!("[tauri] PYTHONPATH from known path: {}", c);
            return c.clone();
        }
    }

    eprintln!("[tauri] WARNING: could not find pratibmb package, using cwd");
    std::env::current_dir()
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_else(|_| ".".to_string())
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
            init_user, import_file, embed, voice, chat_turn,
            extract_profile, finetune, stats, health
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
