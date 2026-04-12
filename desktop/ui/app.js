// Pratibmb frontend.
// When inside Tauri, uses invoke() to reach the Rust backend (which proxies to
// the Python server). In browser dev mode, falls back to direct HTTP to the
// Python server on :11435.

const yearInput = document.getElementById("year");
const yearValue = document.getElementById("year-value");
const chat = document.getElementById("chat");
const composer = document.getElementById("composer");
const input = document.getElementById("input");
const sendBtn = composer.querySelector("button");

const helpBtn = document.getElementById("help-btn");
const helpOverlay = document.getElementById("help-overlay");
const helpClose = document.getElementById("help-close");

helpBtn.addEventListener("click", () => helpOverlay.classList.remove("hidden"));
helpClose.addEventListener("click", () => helpOverlay.classList.add("hidden"));
helpOverlay.addEventListener("click", (e) => {
  if (e.target === helpOverlay) helpOverlay.classList.add("hidden");
});

// Pipeline panel
const pipelineBtn = document.getElementById("pipeline-btn");
const pipelineOverlay = document.getElementById("pipeline-overlay");
const pipelineClose = document.getElementById("pipeline-close");

pipelineBtn.addEventListener("click", () => pipelineOverlay.classList.remove("hidden"));
pipelineClose.addEventListener("click", () => pipelineOverlay.classList.add("hidden"));
pipelineOverlay.addEventListener("click", (e) => {
  if (e.target === pipelineOverlay) pipelineOverlay.classList.add("hidden");
});

const SERVER = "http://127.0.0.1:11435";

const statusBanner = document.getElementById("status-banner");

// Default model paths — auto-discovered by the server.
// Override by setting PRATIBMB_CHAT_MODEL / PRATIBMB_EMBED_MODEL env vars.
const DEFAULTS = {
  model: "",
  embed_model: "",
  chat_format: "gemma",
};

let modelsLoaded = false;

// --------------- Progress polling ---------------

let progressInterval = null;

function startProgressPolling(logId) {
  stopProgressPolling();
  progressInterval = setInterval(async () => {
    try {
      const resp = await fetch(SERVER + "/progress");
      const p = await resp.json();
      if (p.operation) {
        let msg = p.detail || p.operation;
        let pct = -1;
        if (p.total > 0) {
          pct = Math.round((p.current / p.total) * 100);
          msg += ` (${p.current.toLocaleString()}/${p.total.toLocaleString()} — ${pct}%)`;
        }
        updateProgressDisplay(logId, msg, pct);
      }
    } catch {
      // Server may be busy — silently retry next interval
    }
  }, 2000);
}

function stopProgressPolling() {
  if (progressInterval) {
    clearInterval(progressInterval);
    progressInterval = null;
  }
}

function updateProgressDisplay(logId, msg, pct) {
  if (logId === "status-banner") {
    // Chat-mode progress: show in the status banner between chat and composer
    showStatusBanner(msg, pct >= 0 ? pct : undefined);
  } else {
    // Onboarding/pipeline mode: update or append to the log area
    const el = document.getElementById(logId);
    if (!el) return;
    // Look for an existing progress line to update in-place
    const lines = el.textContent.split("\n");
    const lastIdx = lines.length - 1;
    if (lastIdx >= 0 && lines[lastIdx].startsWith("[progress]")) {
      lines[lastIdx] = "[progress] " + msg;
      el.textContent = lines.join("\n");
    } else {
      el.textContent += (el.textContent ? "\n" : "") + "[progress] " + msg;
    }
    el.scrollTop = el.scrollHeight;
  }
}

function showStatusBanner(msg, percent) {
  statusBanner.classList.remove("hidden");
  let html = '<span class="pulsing">' + escapeHtml(msg) + "</span>";
  if (typeof percent === "number" && percent >= 0) {
    html += '<div class="progress-bar"><div class="progress-bar-fill" style="width:' + Math.min(percent, 100) + '%"></div></div>';
  }
  statusBanner.innerHTML = html;
}

function hideStatusBanner() {
  statusBanner.classList.add("hidden");
  statusBanner.innerHTML = "";
}

function escapeHtml(str) {
  const d = document.createElement("div");
  d.textContent = str;
  return d.innerHTML;
}

// --------------- Friendly error messages ---------------

function friendlyChatError(errStr) {
  const lower = errStr.toLowerCase();

  if (lower.includes("chat model not found") || (lower.includes("chat_model") && lower.includes("not found"))) {
    return "The AI model hasn't been downloaded yet. This happens automatically on first use — please wait a moment and try again.";
  }
  if (lower.includes("embed model not found") || (lower.includes("embed_model") && lower.includes("not found"))) {
    return "The embedding model is missing. Click the gear icon to set it up.";
  }
  if (lower.includes("connection refused") || lower.includes("econnrefused") || lower.includes("failed to fetch") || lower.includes("networkerror")) {
    return "Lost connection to the local engine. Please restart the app.";
  }
  if (lower.includes("downloading") || lower.includes("download")) {
    return "A model is being downloaded. This may take a few minutes on first use. Please wait...";
  }

  // Try to extract message from JSON error strings
  try {
    const parsed = JSON.parse(errStr);
    if (parsed.error) return parsed.error;
    if (parsed.detail) return parsed.detail;
    if (parsed.message) return parsed.message;
  } catch {
    // Not JSON — try to clean up "Error: {...}" wrapper
    const jsonMatch = errStr.match(/\{.*\}/s);
    if (jsonMatch) {
      try {
        const parsed = JSON.parse(jsonMatch[0]);
        if (parsed.error) return parsed.error;
        if (parsed.detail) return parsed.detail;
      } catch {}
    }
  }

  return errStr;
}

// --------------- Preflight check ---------------

async function checkPreflight(logId) {
  try {
    const resp = await fetch(SERVER + "/preflight");
    if (!resp.ok) return; // endpoint may not exist yet — skip silently
    const data = await resp.json();
    if (data.warnings && data.warnings.length > 0) {
      for (const w of data.warnings) {
        if (logId) {
          const el = document.getElementById(logId);
          if (el) {
            el.textContent += (el.textContent ? "\n" : "") + "[warning] " + w;
            el.scrollTop = el.scrollHeight;
          }
        }
      }
      return data.warnings;
    }
  } catch {
    // /preflight not available — no problem
  }
  return [];
}

yearInput.addEventListener("input", () => {
  yearValue.textContent = yearInput.value;
});

function appendBubble(kind, text) {
  const div = document.createElement("div");
  div.className = "bubble bubble-" + kind;
  div.textContent = text;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
  return div;
}

function setLoading(on) {
  sendBtn.disabled = on;
  input.disabled = on;
  sendBtn.textContent = on ? "..." : "send";
}

async function invoke(cmd, args) {
  // Always use direct HTTP to the Python server — works in both
  // Tauri webview and browser dev mode. The Rust layer is just a proxy
  // anyway, and direct HTTP avoids Tauri invoke serialization issues.
  const map = {
    init_user: "/init",
    import_file: "/import",
    embed: "/embed",
    voice: "/voice",
    chat_turn: "/chat",
    extract_profile: "/profile",
    finetune: "/finetune",
    stats: "/stats",
    health: "/health",
  };
  const path = map[cmd];
  if (!path) throw new Error("unknown command: " + cmd);
  const method = cmd === "stats" || cmd === "health" ? "GET" : "POST";
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (method === "POST") opts.body = JSON.stringify(args);
  const resp = await fetch(SERVER + path, opts);
  if (!resp.ok) {
    const err = await resp.text();
    throw new Error(err);
  }
  return resp.json();
}

async function chatTurn(year, prompt) {
  const args = {
    year: Number(year),
    prompt,
    model: DEFAULTS.model,
    embed_model: DEFAULTS.embed_model,
    chat_format: DEFAULTS.chat_format,
  };
  return invoke("chat_turn", args);
}

async function checkHealth() {
  // Retry up to 10 times with 1s delay — server may still be starting
  for (let i = 0; i < 10; i++) {
    try {
      await invoke("health", {});
      return true;
    } catch {
      await new Promise((r) => setTimeout(r, 1000));
    }
  }
  return false;
}

// Context hints hidden in normal mode — chat should feel like texting.
// Uncomment for debugging retrieval quality.
// function showContext(used) {
//   if (!used || used.length === 0) return;
//   const summary = used.slice(0, 3)
//     .map((m) => `[${m.year} ${m.thread}] ${m.text.slice(0, 60)}...`).join("\n");
//   const div = document.createElement("div");
//   div.className = "context-hint";
//   div.textContent = "retrieved: " + summary;
//   chat.appendChild(div);
// }
function showContext() {} // no-op

composer.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  appendBubble("you", text);
  setLoading(true);

  // Start polling for progress (model downloads, etc.) — show in status banner
  startProgressPolling("status-banner");

  try {
    const result = await chatTurn(yearInput.value, text);
    appendBubble("past", result.reply);
    showContext(result.used_messages);
  } catch (err) {
    const friendly = friendlyChatError(String(err));
    appendBubble("past", friendly);
  } finally {
    stopProgressPolling();
    hideStatusBanner();
    setLoading(false);
    input.focus();
  }
});

// --------------- Onboarding wizard ---------------

const onboarding = document.getElementById("onboarding");
let obStep = 0;
let obImportCount = 0;

function obShow(step) {
  obStep = step;
  document.querySelectorAll(".ob-step").forEach((el) => {
    el.classList.toggle("hidden", Number(el.dataset.step) !== step);
  });
  document.querySelectorAll(".ob-dot").forEach((dot) => {
    const n = Number(dot.dataset.dot);
    dot.classList.toggle("active", n === step);
    dot.classList.toggle("done", n < step);
  });
}

function obLog(id, text) {
  const el = document.getElementById(id);
  el.textContent += (el.textContent ? "\n" : "") + text;
  el.scrollTop = el.scrollHeight;
}

// Step 0 → 1
document.getElementById("ob-start").addEventListener("click", () => obShow(1));

// Step 1: Name input
const obNameInput = document.getElementById("ob-name");
const obNameNext = document.getElementById("ob-name-next");
obNameInput.addEventListener("input", () => {
  obNameNext.disabled = obNameInput.value.trim().length < 2;
});

obNameNext.addEventListener("click", async () => {
  const name = obNameInput.value.trim();
  obNameNext.disabled = true;
  obNameNext.textContent = "Setting up...";
  const log = document.getElementById("ob-name-log");

  obLog("ob-name-log", "[local] Creating personal database at ~/.pratibmb/corpus.db");
  obLog("ob-name-log", `[local] Registering name: "${name}"`);
  obLog("ob-name-log", "[privacy] Database is local-only. No account created. No signup.");

  try {
    await invoke("init_user", { self_name: name });
    obLog("ob-name-log", "[done] Ready to import your conversations.");
    setTimeout(() => obShow(2), 600);
  } catch (err) {
    obLog("ob-name-log", "[error] " + String(err));
    obNameNext.disabled = false;
    obNameNext.textContent = "Continue";
  }
});

// Step 2: Import
const obDropZone = document.getElementById("ob-drop-zone");
const obImportNext = document.getElementById("ob-import-next");

document.getElementById("ob-browse").addEventListener("click", async () => {
  // Use Tauri file dialog if available, else prompt for path
  const tauri = window.__TAURI__;
  if (tauri?.dialog?.open) {
    const selected = await tauri.dialog.open({
      multiple: false,
      directory: true,
      title: "Select your chat export folder",
    });
    if (selected) {
      await obImportPath(selected);
    }
  } else {
    const path = prompt("Enter the full path to your chat export file or folder:");
    if (path) await obImportPath(path);
  }
});

async function obImportPath(path) {
  obLog("ob-import-log", `\n[local] Importing from: ${path}`);
  obLog("ob-import-log", "[privacy] Reading files directly from disk. Nothing uploaded.");
  obLog("ob-import-log", "[air-gapped] Parsing message format, normalizing timestamps...");

  try {
    const result = await invoke("import_file", { path });
    obImportCount += result.imported || 0;
    obLog("ob-import-log", `[done] Imported ${result.imported} messages (source: ${result.source}).`);
    obLog("ob-import-log", `[local] Total messages so far: ${obImportCount}`);
    obImportNext.disabled = false;
    obImportNext.textContent = `Continue (${obImportCount} messages)`;
  } catch (err) {
    obLog("ob-import-log", "[error] " + String(err));
  }
}

// Drag and drop on the import zone
obDropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  obDropZone.classList.add("dragover");
});
obDropZone.addEventListener("dragleave", () => {
  obDropZone.classList.remove("dragover");
});
obDropZone.addEventListener("drop", async (e) => {
  e.preventDefault();
  obDropZone.classList.remove("dragover");
  // In Tauri, we'd get the file path from the drop event
  const files = e.dataTransfer?.files;
  if (files?.length > 0) {
    const path = files[0].path || files[0].name;
    await obImportPath(path);
  }
});

obImportNext.addEventListener("click", () => obShow(3));
document.getElementById("ob-import-skip").addEventListener("click", () => obShow(3));

// Step 3: Embed
document.getElementById("ob-embed-start").addEventListener("click", async () => {
  const btn = document.getElementById("ob-embed-start");
  btn.disabled = true;
  btn.textContent = "Building...";

  // Pre-operation preflight check
  const warnings = await checkPreflight("ob-embed-log");
  if (warnings && warnings.length > 0) {
    obLog("ob-embed-log", "");  // blank line before starting
  }

  obLog("ob-embed-log", "[air-gapped] Loading embedding model (nomic-embed-text, 84MB)...");
  obLog("ob-embed-log", "[privacy] The model runs on your CPU/GPU. No text is sent anywhere.");
  obLog("ob-embed-log", "[local] Computing vector representations of your messages...");
  obLog("ob-embed-log", "This may take a minute for large corpora.\n");

  // Start polling for real-time progress updates
  startProgressPolling("ob-embed-log");

  try {
    const result = await invoke("embed", { model: "" });
    stopProgressPolling();
    obLog("ob-embed-log", `[done] Embedded ${result.embedded} messages.`);
    obLog("ob-embed-log", "[local] Vectors stored in ~/.pratibmb/corpus.db");
    obLog("ob-embed-log", "[privacy] Zero network requests made during embedding.");
    btn.textContent = "Done!";
    setTimeout(() => obShow(4), 800);
  } catch (err) {
    stopProgressPolling();
    obLog("ob-embed-log", "[error] " + friendlyChatError(String(err)));
    btn.disabled = false;
    btn.textContent = "Retry";
  }
});

// Step 4: Profile
document.getElementById("ob-profile-start").addEventListener("click", async () => {
  const btn = document.getElementById("ob-profile-start");
  btn.disabled = true;
  btn.textContent = "Extracting...";

  obLog("ob-profile-log", "[air-gapped] Loading local LLM (Gemma 3 4B, 2.3GB)...");
  obLog("ob-profile-log", "[privacy] The model runs entirely on your Apple Silicon / CPU.");
  obLog("ob-profile-log", "[privacy] No OpenAI, no cloud APIs, no data leaves this device.\n");
  obLog("ob-profile-log", "Analyzing your conversations to extract:");
  obLog("ob-profile-log", "  - Relationships (who you talk to, how close)");
  obLog("ob-profile-log", "  - Life events (moves, jobs, milestones)");
  obLog("ob-profile-log", "  - Interests (topics you care about)");
  obLog("ob-profile-log", "  - Communication style (formal/casual, emoji use, language mix)");
  obLog("ob-profile-log", "\nThis takes 5-10 minutes. Please be patient...");

  // Start polling for real-time progress updates
  startProgressPolling("ob-profile-log");

  try {
    const result = await invoke("extract_profile", { model: "" });
    stopProgressPolling();
    obLog("ob-profile-log", `\n[done] Profile extracted!`);
    obLog("ob-profile-log", `  ${result.relationships || 0} relationships found`);
    obLog("ob-profile-log", `  ${result.life_events || 0} life events detected`);
    obLog("ob-profile-log", `  ${result.year_summaries || 0} year summaries built`);
    obLog("ob-profile-log", `\n[local] Profile saved to local database.`);
    obLog("ob-profile-log", "[privacy] Your identity data never leaves this machine.");
    btn.textContent = "Done!";
    setTimeout(() => obFinish(), 800);
  } catch (err) {
    stopProgressPolling();
    obLog("ob-profile-log", "[error] " + friendlyChatError(String(err)));
    btn.disabled = false;
    btn.textContent = "Retry";
  }
});

document.getElementById("ob-profile-skip").addEventListener("click", () => obFinish());

async function obFinish() {
  // Build summary
  try {
    const s = await invoke("stats", {});
    const summary = document.getElementById("ob-summary");
    summary.innerHTML = `
      <b>${s.total.toLocaleString()}</b> messages imported<br>
      <b>${s.self_total.toLocaleString()}</b> of those are yours<br>
      ${s.has_profile ? "Profile extracted" : "Profile not yet extracted (do it from the gear icon)"}
    `;
  } catch {}
  obShow(5);
}

// Step 5: Done
document.getElementById("ob-done").addEventListener("click", () => {
  onboarding.classList.add("hidden");
});

// --------------- Pipeline panel logic ---------------

function statusEl(id) {
  return document.getElementById(id);
}

function setStepStatus(id, text, state) {
  const el = statusEl(id);
  el.textContent = text;
  el.className = "step-status step-" + state; // running, done, error
}

function appendLog(id, line) {
  const el = statusEl(id);
  el.textContent += (el.textContent ? "\n" : "") + line;
  el.scrollTop = el.scrollHeight;
}

function disableBtn(id, disabled) {
  document.getElementById(id).disabled = disabled;
}

// Step 1: Profile extraction
document.getElementById("btn-profile").addEventListener("click", async () => {
  disableBtn("btn-profile", true);
  setStepStatus("profile-status", "Starting profile extraction...\nThis analyzes your messages 100% locally on your machine — nothing leaves this device.", "running");

  appendLog("profile-status", "\n[air-gapped] Loading local LLM for analysis...");
  appendLog("profile-status", "[privacy] Your messages are read directly from the local database.");
  appendLog("profile-status", "[privacy] No API calls. No cloud. No telemetry.\n");
  appendLog("profile-status", "Extracting relationships, life events, interests...");
  appendLog("profile-status", "This takes 5-10 minutes. The LLM reads batches of your messages to build a structured identity profile.\n");

  startProgressPolling("profile-status");

  try {
    const result = await invoke("extract_profile", { model: "" });
    stopProgressPolling();
    appendLog("profile-status", `\nDone! Found:`);
    appendLog("profile-status", `  ${result.relationships || 0} relationships`);
    appendLog("profile-status", `  ${result.life_events || 0} life events`);
    appendLog("profile-status", `  ${result.year_summaries || 0} year summaries`);
    appendLog("profile-status", `\n[local] Profile saved to ~/.pratibmb/corpus.db — never uploaded anywhere.`);
    setStepStatus("profile-status", statusEl("profile-status").textContent, "done");
  } catch (err) {
    stopProgressPolling();
    appendLog("profile-status", "\nError: " + friendlyChatError(String(err)));
    setStepStatus("profile-status", statusEl("profile-status").textContent, "error");
  }
  disableBtn("btn-profile", false);
});

// Step 2: Extract training pairs
document.getElementById("btn-extract").addEventListener("click", async () => {
  disableBtn("btn-extract", true);
  setStepStatus("extract-status", "Extracting training pairs from your conversations...\n", "running");

  appendLog("extract-status", "[air-gapped] Scanning local message database for conversation patterns.");
  appendLog("extract-status", "[privacy] Training data stays in ~/.pratibmb/finetune/data/ — never committed to git, never uploaded.");
  appendLog("extract-status", "[privacy] Only natural reply-pairs (friend says X → you reply Y) are extracted.\n");
  appendLog("extract-status", "Filtering: removing media-only, URLs, system messages, duplicates...");

  try {
    const result = await invoke("finetune", { step: "extract" });
    if (result.status === "error") {
      appendLog("extract-status", "\nError: " + (result.error || "no training pairs found"));
      setStepStatus("extract-status", statusEl("extract-status").textContent, "error");
    } else {
      appendLog("extract-status", `\nExtracted ${result.pairs} conversation pairs.`);
      appendLog("extract-status", `Formatted for Gemma 3 chat template.`);
      appendLog("extract-status", `Split: ${result.train} training + ${result.val} validation records.`);
      appendLog("extract-status", `\n[local] Saved to: ${result.data_dir}`);
      appendLog("extract-status", `[privacy] .gitignore blocks these files from ever being committed.`);
      setStepStatus("extract-status", statusEl("extract-status").textContent, "done");
    }
  } catch (err) {
    appendLog("extract-status", "\nError: " + friendlyChatError(String(err)));
    setStepStatus("extract-status", statusEl("extract-status").textContent, "error");
  }
  disableBtn("btn-extract", false);
});

// Step 3: Fine-tune
document.getElementById("btn-train").addEventListener("click", async () => {
  disableBtn("btn-train", true);
  setStepStatus("train-status", "Starting LoRA fine-tuning...\n", "running");

  appendLog("train-status", "[air-gapped] Training runs entirely on your Apple Silicon GPU via MLX.");
  appendLog("train-status", "[privacy] The base model (Gemma 3 4B) is downloaded once from HuggingFace,");
  appendLog("train-status", "         then cached locally. No data is ever sent upstream.");
  appendLog("train-status", "[privacy] The adapter learns YOUR voice — it stays on your machine.\n");
  appendLog("train-status", "Config: rank 8, lr 2e-5, 16 layers, ~500 iterations");
  appendLog("train-status", "Estimated time: 20-30 minutes on M-series Mac.\n");
  appendLog("train-status", "Training in progress...");

  startProgressPolling("train-status");

  try {
    const result = await invoke("finetune", { step: "train" });
    stopProgressPolling();
    if (result.status === "ok") {
      appendLog("train-status", `\nTraining complete!`);
      appendLog("train-status", `Adapter saved to: ${result.adapter_path}`);
      appendLog("train-status", `\n[local] 114MB LoRA adapter — captures your texting style.`);
      setStepStatus("train-status", statusEl("train-status").textContent, "done");
    } else if (result.status === "manual") {
      appendLog("train-status", `\nmlx-lm not installed. Manual instructions:\n${result.instructions}`);
      setStepStatus("train-status", statusEl("train-status").textContent, "error");
    } else {
      appendLog("train-status", "\nError: " + (result.error || "training failed"));
      setStepStatus("train-status", statusEl("train-status").textContent, "error");
    }
  } catch (err) {
    stopProgressPolling();
    appendLog("train-status", "\nError: " + friendlyChatError(String(err)));
    setStepStatus("train-status", statusEl("train-status").textContent, "error");
  }
  disableBtn("btn-train", false);
});

// Step 4: Convert
document.getElementById("btn-convert").addEventListener("click", async () => {
  disableBtn("btn-convert", true);
  setStepStatus("convert-status", "Converting adapter to GGUF format...\n", "running");

  appendLog("convert-status", "[air-gapped] Conversion runs locally using llama.cpp tools.");
  appendLog("convert-status", "[privacy] The GGUF adapter is saved to ~/.pratibmb/models/");
  appendLog("convert-status", "         and auto-loaded by the chat engine on next restart.\n");

  try {
    const result = await invoke("finetune", { step: "convert" });
    if (result.status === "ok") {
      appendLog("convert-status", `Converted! GGUF adapter: ${result.output_path}`);
      appendLog("convert-status", `\nRestart the app to load the fine-tuned model.`);
      appendLog("convert-status", `[local] Your digital twin now speaks in your voice.`);
      setStepStatus("convert-status", statusEl("convert-status").textContent, "done");
    } else if (result.status === "manual") {
      appendLog("convert-status", `\nAutomatic conversion unavailable. Instructions:\n${result.instructions}`);
      setStepStatus("convert-status", statusEl("convert-status").textContent, "error");
    } else {
      appendLog("convert-status", "\nError: " + (result.error || "conversion failed"));
      setStepStatus("convert-status", statusEl("convert-status").textContent, "error");
    }
  } catch (err) {
    appendLog("convert-status", "\nError: " + friendlyChatError(String(err)));
    setStepStatus("convert-status", statusEl("convert-status").textContent, "error");
  }
  disableBtn("btn-convert", false);
});

// --------------- Diagnostics / Log export ---------------

async function fetchLogs() {
  try {
    const resp = await fetch(SERVER + "/logs");
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

function formatLogReport(data) {
  const sys = data.system || {};
  let report = "=== Pratibmb Bug Report ===\n\n";
  report += "--- System Info ---\n";
  report += "OS: " + (sys.os || "unknown") + "\n";
  report += "Arch: " + (sys.arch || "unknown") + "\n";
  report += "Python: " + (sys.python || "unknown") + "\n";
  report += "Disk Free: " + (sys.disk_free_gb || "?") + " GB\n";
  report += "Data Dir: " + (sys.pratibmb_data || "unknown") + "\n";
  report += "Log Dir: " + (data.log_dir || "unknown") + "\n\n";

  if (data.lines && data.lines.length > 0) {
    report += "--- Recent Python Logs (last " + data.lines.length + " lines) ---\n";
    report += data.lines.join("\n") + "\n\n";
  }

  if (data.tauri_lines && data.tauri_lines.length > 0) {
    report += "--- Recent Tauri Logs (last " + data.tauri_lines.length + " lines) ---\n";
    report += data.tauri_lines.join("\n") + "\n";
  }

  return report;
}

function showDiagStatus(msg, isError) {
  const el = document.getElementById("diag-status");
  el.textContent = msg;
  el.className = "diag-status" + (isError ? " diag-error" : "");
  el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), 4000);
}

// Report Issue — collects logs + system info, opens mailto
document.getElementById("btn-report-issue").addEventListener("click", async () => {
  const btn = document.getElementById("btn-report-issue");
  btn.disabled = true;
  btn.textContent = "Collecting logs...";

  const data = await fetchLogs();
  btn.disabled = false;
  btn.textContent = "Report Issue";

  if (!data) {
    showDiagStatus("Could not collect logs. Is the server running?", true);
    return;
  }

  const report = formatLogReport(data);

  // Copy to clipboard first (email body has length limits)
  try {
    await navigator.clipboard.writeText(report);
  } catch {}

  // Open mailto with pre-filled subject and a note to paste
  const subject = encodeURIComponent("Pratibmb Bug Report");
  const body = encodeURIComponent(
    "Please describe what went wrong:\n\n\n" +
    "---\n" +
    "(Diagnostic logs have been copied to your clipboard. Press Ctrl+V / Cmd+V to paste them below.)\n\n" +
    report.slice(0, 1500) + "\n\n[Full logs copied to clipboard]"
  );
  window.open("mailto:admin@sparkupcloud.com?subject=" + subject + "&body=" + body);
  showDiagStatus("Logs copied to clipboard. Paste them in the email.", false);
});

// Copy Logs — copies full log content to clipboard
document.getElementById("btn-copy-logs").addEventListener("click", async () => {
  const btn = document.getElementById("btn-copy-logs");
  btn.disabled = true;
  btn.textContent = "Copying...";

  const data = await fetchLogs();
  btn.disabled = false;
  btn.textContent = "Copy Logs";

  if (!data) {
    showDiagStatus("Could not collect logs.", true);
    return;
  }

  const report = formatLogReport(data);
  try {
    await navigator.clipboard.writeText(report);
    showDiagStatus("Logs copied to clipboard!", false);
  } catch {
    showDiagStatus("Could not copy to clipboard.", true);
  }
});

// Open Log Folder — opens the log directory in the file manager
document.getElementById("btn-open-logs").addEventListener("click", async () => {
  const data = await fetchLogs();
  if (data && data.log_dir) {
    // Try using Tauri shell plugin to open the folder
    const tauri = window.__TAURI__;
    if (tauri?.shell?.open) {
      await tauri.shell.open(data.log_dir);
    } else {
      // Fallback: show the path
      showDiagStatus("Log folder: " + data.log_dir, false);
    }
  } else {
    showDiagStatus("Log dir: ~/.pratibmb/logs/", false);
  }
});

// On load: check server health, show onboarding or chat
(async () => {
  try {
    const ok = await checkHealth();
    if (!ok) {
      chat.innerHTML = "";
      const errorDiv = document.createElement("div");
      errorDiv.className = "bubble bubble-past startup-error";
      errorDiv.textContent =
        "Could not connect to the Pratibmb engine.\n\n" +
        "This usually means Python 3.10+ is not installed or the pratibmb package is missing.\n\n" +
        "To fix:\n" +
        "1. Install Python 3.10+ from python.org\n" +
        "2. Run: pip install -e /path/to/Pratibmb\n\n" +
        "Then restart the app.";
      chat.appendChild(errorDiv);
      return;
    }

    const s = await invoke("stats", {});
    chat.innerHTML = ""; // clear default HTML bubble

    if (s.total === 0) {
      // First run — show onboarding wizard
      onboarding.classList.remove("hidden");
    } else {
      // Returning user
      let msg = `ready. ${s.self_total} of your messages loaded. pick a year and ask away.`;
      if (s.has_profile) {
        msg += " profile loaded.";
      } else {
        msg += " tip: click the gear icon to extract your profile and fine-tune.";
      }
      appendBubble("past", msg);
    }
  } catch (err) {
    chat.innerHTML = "";
    const friendly = friendlyChatError(String(err));
    appendBubble("past", friendly);
  }
})();
