// Minimal frontend. When running inside Tauri, `window.__TAURI__.core.invoke`
// is available and we use it to reach the Rust backend. In plain-browser dev
// mode we fall back to a local stub so the UI is still clickable.

const yearInput = document.getElementById("year");
const yearValue = document.getElementById("year-value");
const chat = document.getElementById("chat");
const composer = document.getElementById("composer");
const input = document.getElementById("input");

yearInput.addEventListener("input", () => {
  yearValue.textContent = yearInput.value;
});

function appendBubble(kind, text) {
  const div = document.createElement("div");
  div.className = "bubble bubble-" + kind;
  div.textContent = text;
  chat.appendChild(div);
  chat.scrollTop = chat.scrollHeight;
}

async function chatTurn(year, prompt) {
  const tauri = window.__TAURI__?.core?.invoke;
  if (tauri) {
    return tauri("chat_turn", { args: { year: Number(year), prompt } });
  }
  // Browser fallback for UI development.
  await new Promise((r) => setTimeout(r, 300));
  return {
    reply: `(browser stub) you in ${year} would probably say something honest here.`,
    used_messages: [],
  };
}

composer.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  appendBubble("you", text);
  try {
    const result = await chatTurn(yearInput.value, text);
    appendBubble("past", result.reply);
  } catch (err) {
    appendBubble("past", "[error] " + String(err));
  }
});
