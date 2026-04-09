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

const SERVER = "http://127.0.0.1:11435";

// Default model paths (overridable via settings later)
const DEFAULTS = {
  model: "/Volumes/wininstall/llm-eval/models/gemma-3-4b-it-q4_k_m.gguf",
  embed_model: "/Volumes/wininstall/llm-eval/models/nomic-embed-text-v1.5-q4_k_m.gguf",
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

// On load: check server health
(async () => {
  const ok = await checkHealth();
  if (ok) {
    const s = await invoke("stats", {});
    if (s.total > 0) {
      appendBubble("past", `ready. ${s.self_total} of your messages loaded. pick a year and ask away.`);
    }
  }
})();
