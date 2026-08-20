/* ============================================================
   YILMAZ BANK — app.js
   Gerçek sohbet akışı: mesajlar biriktirilir, altta sabit
   composer'dan gönderilir, her assistant mesajı kendi tool
   trace'ini katlanır şekilde içinde taşır.

   Backend sözleşmesi (app.py bunu karşılayacak):

   POST /api/query
   Body:  { "query": "<kullanıcı isteği>" }
   Yanıt: {
     "answer": "<nihai cevap metni>",
     "status": { "state": "ok" | "warn" | "pending", "text": "<özet>" },
     "trace": [
       {
         "turn": 1,
         "thinking": "<ya da null>",
         "tool_calls": [
           { "tool_name": "...", "arguments": {...}, "success": true, "result": {...}, "error": null }
         ]
       }
     ]
   }
   ============================================================ */

const emptyState = document.getElementById("empty-state");
const messagesEl = document.getElementById("messages");
const thread = document.getElementById("thread");
const composer = document.getElementById("composer");
const queryInput = document.getElementById("query-input");
const submitButton = document.getElementById("submit-button");
const suggestionGrid = document.getElementById("suggestion-grid");

let hasStarted = false;

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value;
  return div.innerHTML;
}

function formatValue(value) {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}

function scrollToBottom() {
  thread.scrollTop = thread.scrollHeight;
}

function startThreadIfNeeded() {
  if (hasStarted) return;
  hasStarted = true;
  emptyState.classList.add("is-hidden");
}

function autoResizeTextarea() {
  queryInput.style.height = "auto";
  queryInput.style.height = Math.min(queryInput.scrollHeight, 140) + "px";
}

function appendUserMessage(text) {
  const msg = document.createElement("div");
  msg.className = "msg msg-user";
  msg.innerHTML = `<div class="bubble">${escapeHtml(text)}</div>`;
  messagesEl.appendChild(msg);
  scrollToBottom();
}

function appendPendingAssistantMessage() {
  const msg = document.createElement("div");
  msg.className = "msg msg-assistant msg-pending";
  msg.innerHTML = `
    <div class="bubble">
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
    </div>
  `;
  messagesEl.appendChild(msg);
  scrollToBottom();
  return msg;
}

function buildTracePanelHtml(trace) {
  if (!trace || trace.length === 0) return "";

  const parts = [];

  trace.forEach((turn) => {
    parts.push('<div class="trace-turn">');

    if (turn.thinking) {
      parts.push(`<div class="trace-thinking">${escapeHtml(turn.thinking)}</div>`);
    }

    const calls = turn.tool_calls || [];

    if (calls.length === 0) {
      return; 
    }

    calls.forEach((call) => {
      const statusClass = call.success ? "ok" : "fail";
      parts.push(
        `<div class="trace-line"><span class="k">TOOL</span><span class="v trace-tool-name ${statusClass}">${escapeHtml(call.tool_name)}</span></div>`
      );
      parts.push(
        `<div class="trace-line"><span class="k">ARGS</span><span class="v">${escapeHtml(formatValue(call.arguments))}</span></div>`
      );
      if (call.success) {
        parts.push(
          `<div class="trace-line"><span class="k">SONUÇ</span><span class="v">${escapeHtml(formatValue(call.result))}</span></div>`
        );
      } else {
        parts.push(
          `<div class="trace-line"><span class="k">HATA</span><span class="v">${escapeHtml(formatValue(call.error))}</span></div>`
        );
      }
    });

    parts.push("</div>");
  });

  return parts.join("");
}

function countToolCalls(trace) {
  if (!trace) return 0;
  return trace.reduce((sum, turn) => sum + (turn.tool_calls ? turn.tool_calls.length : 0), 0);
}

function replaceWithAssistantMessage(pendingEl, data) {
  const toolCount = countToolCalls(data.trace);
  const statusState = (data.status && data.status.state) || "ok";
  const isWarn = statusState === "warn";

  const traceHtml = buildTracePanelHtml(data.trace);
  const hasTrace = toolCount > 0;

  pendingEl.classList.remove("msg-pending");
  pendingEl.innerHTML = `
    <div class="bubble">
      <div class="answer-text">${escapeHtml(data.answer || "Bir cevap alınamadı.")}</div>
      ${hasTrace ? `
        <button class="trace-toggle" type="button" aria-expanded="false">
          <span class="chevron" aria-hidden="true">▶</span>
          ${toolCount} tool çağrısı
        </button>
        <div class="trace-panel">${traceHtml}</div>
      ` : ""}
      ${data.status && data.status.text ? `
        <div class="meta-line ${isWarn ? "is-warn" : ""}">${isWarn ? "⚠" : "·"} ${escapeHtml(data.status.text)}</div>
      ` : ""}
    </div>
  `;

  const toggle = pendingEl.querySelector(".trace-toggle");
  const panel = pendingEl.querySelector(".trace-panel");
  if (toggle && panel) {
    toggle.addEventListener("click", () => {
      const isOpen = panel.classList.toggle("is-open");
      toggle.setAttribute("aria-expanded", String(isOpen));
    });
  }

  scrollToBottom();
}

function showErrorMessage(pendingEl, errorText) {
  pendingEl.classList.remove("msg-pending");
  pendingEl.innerHTML = `
    <div class="bubble">
      <div class="answer-text">İsteğiniz işlenemedi.</div>
      <div class="meta-line is-warn">⚠ ${escapeHtml(errorText)}</div>
    </div>
  `;
  scrollToBottom();
}

async function sendQuery(query) {
  startThreadIfNeeded();
  appendUserMessage(query);

  queryInput.value = "";
  autoResizeTextarea();
  submitButton.disabled = true;

  const pendingEl = appendPendingAssistantMessage();

  try {
    const response = await fetch("/api/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });

    if (!response.ok) {
      throw new Error(`Sunucu hatası: ${response.status}`);
    }

    const data = await response.json();
    replaceWithAssistantMessage(pendingEl, data);
  } catch (error) {
    showErrorMessage(pendingEl, error.message);
  } finally {
    submitButton.disabled = false;
    queryInput.focus();
  }
}

composer.addEventListener("submit", (event) => {
  event.preventDefault();
  const query = queryInput.value.trim();
  if (!query) return;
  sendQuery(query);
});

queryInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    composer.requestSubmit();
  }
});

queryInput.addEventListener("input", autoResizeTextarea);

if (suggestionGrid) {
  suggestionGrid.addEventListener("click", (event) => {
    const card = event.target.closest(".suggestion");
    if (!card) return;
    const query = card.dataset.query || card.textContent.trim();
    sendQuery(query);
  });
}

queryInput.focus();