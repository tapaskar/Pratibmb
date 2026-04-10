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

// Default model paths — auto-discovered by the server.
// Override by setting PRATIBMB_CHAT_MODEL / PRATIBMB_EMBED_MODEL env vars.
const DEFAULTS = {
  model: "",
  embed_model: "",
  chat_format: "gemma",
};

let modelsLoaded = false;

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
  const tauri = window.__TAURI__?.core?.invoke;
  if (tauri) {
    return tauri(cmd, { args });
  }
  // Browser fallback: talk directly to the Python server
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
  try {
    await invoke("health", {});
    return true;
  } catch {
    return false;
  }
}

async function showContext(used) {
  if (!used || used.length === 0) return;
  const summary = used
    .slice(0, 3)
    .map((m) => `[${m.year} ${m.thread}] ${m.text.slice(0, 60)}...`)
    .join("\n");
  const div = document.createElement("div");
  div.className = "context-hint";
  div.textContent = "retrieved: " + summary;
  chat.appendChild(div);
}

composer.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  appendBubble("you", text);
  setLoading(true);
  try {
    const result = await chatTurn(yearInput.value, text);
    appendBubble("past", result.reply);
    showContext(result.used_messages);
  } catch (err) {
    appendBubble("past", "[error] " + String(err));
  } finally {
    setLoading(false);
    input.focus();
  }
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

  try {
    const result = await invoke("extract_profile", { model: "" });
    appendLog("profile-status", `\nDone! Found:`);
    appendLog("profile-status", `  ${result.relationships || 0} relationships`);
    appendLog("profile-status", `  ${result.life_events || 0} life events`);
    appendLog("profile-status", `  ${result.year_summaries || 0} year summaries`);
    appendLog("profile-status", `\n[local] Profile saved to ~/.pratibmb/corpus.db — never uploaded anywhere.`);
    setStepStatus("profile-status", statusEl("profile-status").textContent, "done");
  } catch (err) {
    appendLog("profile-status", "\nError: " + String(err));
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
    appendLog("extract-status", "\nError: " + String(err));
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
  appendLog("train-status", "Training in progress... (this window will update when done)");

  try {
    const result = await invoke("finetune", { step: "train" });
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
    appendLog("train-status", "\nError: " + String(err));
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
    appendLog("convert-status", "\nError: " + String(err));
    setStepStatus("convert-status", statusEl("convert-status").textContent, "error");
  }
  disableBtn("btn-convert", false);
});

// On load: check server health and profile status
(async () => {
  const ok = await checkHealth();
  if (ok) {
    const s = await invoke("stats", {});
    if (s.total > 0) {
      let msg = `ready. ${s.self_total} of your messages loaded. pick a year and ask away.`;
      if (s.has_profile) {
        msg += " profile loaded.";
      } else {
        msg += " tip: click the gear icon to extract your profile and fine-tune.";
      }
      appendBubble("past", msg);
    }
  }
})();
