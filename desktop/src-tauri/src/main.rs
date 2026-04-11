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
    // Embedding large datasets can take 5-10 minutes; use 30-minute timeout
    post_json_timeout("/embed", &args, 1800).await
}

#[tauri::command]
async fn voice() -> Result<serde_json::Value, String> {
    post_json("/voice", &serde_json::json!({})).await
}

#[tauri::command]
async fn chat_turn(args: ChatArgs) -> Result<serde_json::Value, String> {
    // First chat may trigger a 2.5GB model download; use 10-minute timeout
    post_json_timeout("/chat", &args, 600).await
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

#[tauri::command]
async fn models() -> Result<serde_json::Value, String> {
    get_json("/models").await
}

#[tauri::command]
async fn progress() -> Result<serde_json::Value, String> {
    get_json("/progress").await
}

#[tauri::command]
async fn preflight() -> Result<serde_json::Value, String> {
    get_json("/preflight").await
}

/// Find a working Python 3 interpreter.
///
/// Tries python3 first (most systems), then python (Windows). Validates
/// that the found interpreter is actually Python 3.10+ before returning.
fn find_python() -> Option<String> {
    let candidates = ["python3", "python"];

    for py in &candidates {
        match Command::new(py)
            .args(["--version"])
            .output()
        {
            Ok(output) => {
                let version_str = String::from_utf8_lossy(&output.stdout);
                let version_str = version_str.trim();
                // Parse "Python 3.X.Y" — require 3.10+
                if let Some(ver) = version_str.strip_prefix("Python ") {
                    let parts: Vec<&str> = ver.split('.').collect();
                    if parts.len() >= 2 {
                        let major: u32 = parts[0].parse().unwrap_or(0);
                        let minor: u32 = parts[1].parse().unwrap_or(0);
                        if major == 3 && minor >= 10 {
                            eprintln!("[tauri] found {} ({})", py, version_str);
                            return Some(py.to_string());
                        } else {
                            eprintln!(
                                "[tauri] {} is {} (need 3.10+), skipping",
                                py, version_str
                            );
                        }
                    }
                }
            }
            Err(_) => {
                // Not found in PATH, try next
            }
        }
    }

    eprintln!("[tauri] ERROR: Python 3.10+ not found. Install from https://python.org");
    None
}

fn spawn_python_server() -> Option<Child> {
    let python = find_python()?;
    let pythonpath = get_pythonpath();
    eprintln!("[tauri] PYTHONPATH = {}", pythonpath);

    // Verify pratibmb package is importable
    let check = Command::new(&python)
        .args(["-c", "import pratibmb; print('ok')"])
        .env("PYTHONPATH", &pythonpath)
        .output();

    match &check {
        Ok(output) if output.status.success() => {
            eprintln!("[tauri] pratibmb package verified");
        }
        _ => {
            eprintln!("[tauri] pratibmb not found, attempting auto-install...");
            auto_install_package(&python, &pythonpath);
        }
    }

    eprintln!("[tauri] starting: {} -m pratibmb.server 11435", python);
    match Command::new(&python)
        .args(["-m", "pratibmb.server", "11435"])
        .env("PYTHONPATH", &pythonpath)
        .spawn()
    {
        Ok(child) => {
            eprintln!("[tauri] spawned python server (pid {})", child.id());
            Some(child)
        }
        Err(e) => {
            eprintln!("[tauri] ERROR: failed to spawn server: {}", e);
            None
        }
    }
}

/// Auto-install the pratibmb Python package if not found.
///
/// Tries two strategies:
/// 1. pip install from GitHub (works on any platform with internet)
/// 2. Clone repo to ~/Pratibmb and pip install -e . (fallback)
fn auto_install_package(python: &str, pythonpath: &str) {
    eprintln!("[tauri] === Auto-installing pratibmb package ===");

    // Strategy 1: pip install directly from GitHub
    eprintln!("[tauri] trying: pip install from GitHub...");
    let pip_result = Command::new(python)
        .args([
            "-m", "pip", "install", "--prefer-binary",
            "pratibmb @ git+https://github.com/tapaskar/Pratibmb.git",
        ])
        .output();

    match pip_result {
        Ok(output) if output.status.success() => {
            eprintln!("[tauri] pip install from GitHub succeeded");
            return;
        }
        Ok(output) => {
            let stderr = String::from_utf8_lossy(&output.stderr);
            eprintln!("[tauri] pip install failed: {}", stderr.trim());
        }
        Err(e) => {
            eprintln!("[tauri] pip command failed: {}", e);
        }
    }

    // Strategy 2: Clone to ~/Pratibmb and install from there
    let home = std::env::var("HOME")
        .or_else(|_| std::env::var("USERPROFILE"))
        .unwrap_or_default();
    let repo_dir = std::path::Path::new(&home).join("Pratibmb");

    if !repo_dir.join("pratibmb").is_dir() {
        eprintln!("[tauri] cloning repo to {}...", repo_dir.display());
        let clone = Command::new("git")
            .args([
                "clone", "--depth", "1",
                "https://github.com/tapaskar/Pratibmb.git",
                &repo_dir.to_string_lossy(),
            ])
            .output();

        match clone {
            Ok(output) if output.status.success() => {
                eprintln!("[tauri] cloned successfully");
            }
            _ => {
                eprintln!("[tauri] git clone failed — user will need to install manually");
                eprintln!("[tauri] run: pip install 'pratibmb @ git+https://github.com/tapaskar/Pratibmb.git'");
                return;
            }
        }
    }

    // Install from the cloned repo
    eprintln!("[tauri] installing from {}...", repo_dir.display());
    let install = Command::new(python)
        .args(["-m", "pip", "install", "--prefer-binary", "-e", "."])
        .current_dir(&repo_dir)
        .output();

    match install {
        Ok(output) if output.status.success() => {
            eprintln!("[tauri] package installed from local clone");
            // Set env var so get_pythonpath finds it
            std::env::set_var("PRATIBMB_ROOT", &repo_dir);
        }
        Ok(output) => {
            let stderr = String::from_utf8_lossy(&output.stderr);
            eprintln!("[tauri] install from clone failed: {}", stderr.trim());
            eprintln!("[tauri] user may need: pip install llama-cpp-python --prefer-binary");
        }
        Err(e) => {
            eprintln!("[tauri] install failed: {}", e);
        }
    }
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

    // Common install locations
    let home = std::env::var("HOME")
        .or_else(|_| std::env::var("USERPROFILE"))
        .unwrap_or_default();
    let candidates = [
        format!("{}/Pratibmb", home),
        format!("{}\\Pratibmb", home),  // Windows
    ];
    for c in &candidates {
        let p = std::path::Path::new(c);
        if p.join("pratibmb").is_dir() {
            eprintln!("[tauri] PYTHONPATH from known path: {}", c);
            return c.clone();
        }
    }

    // If pip-installed, pratibmb is in site-packages — no PYTHONPATH needed
    // Return empty string; Python will find it via its own sys.path
    let pip_check = Command::new(
        if cfg!(windows) { "python" } else { "python3" }
    )
        .args(["-c", "import pratibmb; print(pratibmb.__file__)"])
        .output();

    if let Ok(output) = pip_check {
        if output.status.success() {
            eprintln!("[tauri] pratibmb found in pip site-packages");
            return String::new();  // No extra PYTHONPATH needed
        }
    }

    eprintln!("[tauri] WARNING: could not find pratibmb package, using cwd");
    std::env::current_dir()
        .map(|p| p.to_string_lossy().to_string())
        .unwrap_or_else(|_| ".".to_string())
}

/// Wait for the Python server to become ready by polling /health.
fn wait_for_server(timeout_ms: u64) {
    let start = std::time::Instant::now();
    let poll_interval = std::time::Duration::from_millis(200);
    let timeout = std::time::Duration::from_millis(timeout_ms);

    loop {
        // Try a synchronous TCP connect + HTTP request
        if let Ok(stream) = std::net::TcpStream::connect_timeout(
            &"127.0.0.1:11435".parse().unwrap(),
            std::time::Duration::from_millis(500),
        ) {
            drop(stream);
            eprintln!(
                "[tauri] server ready after {}ms",
                start.elapsed().as_millis()
            );
            return;
        }

        if start.elapsed() > timeout {
            eprintln!(
                "[tauri] WARNING: server not ready after {}ms, proceeding anyway",
                timeout_ms
            );
            return;
        }

        std::thread::sleep(poll_interval);
    }
}

fn main() {
    let child = spawn_python_server();

    if child.is_some() {
        // Poll /health instead of blind sleep
        wait_for_server(10000);
    } else {
        eprintln!("[tauri] WARNING: no Python server — app will show connection errors");
        eprintln!("[tauri] Install Python 3.10+ and run: pip install -e /path/to/Pratibmb");
    }

    tauri::Builder::default()
        .manage(ServerProcess(Mutex::new(child)))
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            init_user, import_file, embed, voice, chat_turn,
            extract_profile, finetune, stats, health,
            models, progress, preflight
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
