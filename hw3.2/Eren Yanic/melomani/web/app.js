// Browser front end.
//
// This file owns the DOM and nothing else. The catalogue, the tools, the router
// and the agent loop are the same modules scripts/demo.mjs runs under Node —
// the only substitution is the database adapter.

import { openDatabase } from '../db/adapter.browser.js';
import { viewCart } from '../db/repository.js';
import { runTurn, MODELS, DEFAULT_MODEL, InferenceError } from '../agent/loop.js';

const $ = (id) => document.getElementById(id);

const el = {
  messages: $('messages'),
  composer: $('composer'),
  input: $('input'),
  send: $('send'),
  gate: $('token-gate'),
  tokenForm: $('token-form'),
  token: $('token'),
  model: $('model'),
  trace: $('trace'),
  tracePanel: $('trace-panel'),
  traceToggle: $('trace-toggle'),
  traceClear: $('trace-clear'),
  reset: $('reset'),
  status: $('status'),
  cart: $('cart-summary'),
};

const STORE = { token: 'melomani.token', session: 'melomani.session', model: 'melomani.model' };

// One session id per browser, so the cart survives a reload.
function sessionId() {
  let id = localStorage.getItem(STORE.session);
  if (!id) {
    id = `web-${crypto.randomUUID()}`;
    localStorage.setItem(STORE.session, id);
  }
  return id;
}

// The context object is created once and threaded through every turn: it
// carries turnId and the checkout gate, which only mean anything across turns.
let context = null;
let history = [];
let busy = false;

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

// Just enough markdown for what the models actually emit: **bold** and `code`.
function lightMarkdown(text) {
  return escapeHtml(text)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>');
}

function addMessage(role, text, { error = false } = {}) {
  const wrap = document.createElement('div');
  wrap.className = `msg ${role}${error ? ' error' : ''}`;
  wrap.innerHTML = `<div class="who">${role === 'user' ? 'siz' : 'm'}</div>`
    + `<div class="body">${lightMarkdown(text)}</div>`;
  el.messages.appendChild(wrap);
  scrollDown();
  return wrap;
}

function addThinking() {
  const wrap = document.createElement('div');
  wrap.className = 'msg assistant';
  wrap.innerHTML = '<div class="who">m</div>'
    + '<div class="body"><span class="dots"><span></span><span></span><span></span></span></div>';
  el.messages.appendChild(wrap);
  scrollDown();
  return wrap;
}

function scrollDown() {
  el.messages.scrollTop = el.messages.scrollHeight;
}

function welcome() {
  const box = document.createElement('div');
  box.className = 'welcome';
  box.innerHTML = `
    <h2>Merhaba — welcome</h2>
    <p>A shop assistant with no memory of its own stock. Ask it something, and watch the
    tool calls on the right: every album, price and order in its answers came back from
    a real SQLite database running in this page.</p>
    <ul>
      <li><code>Ağır ve hızlı bir şey arıyorum, thrash metal var mı?</code></li>
      <li><code>I like Darkthrone — what else have you got?</code></li>
      <li><code>Pink Floyd severim, benzer bir şey önerir misin?</code></li>
      <li><code>What jazz do you have under 350 lira?</code></li>
      <li><code>Do you sell Taylor Swift?</code> — it will tell you no, rather than invent one</li>
    </ul>`;
  el.messages.appendChild(box);
}

// ---------------------------------------------------------------------------
// Trace panel
// ---------------------------------------------------------------------------

let lastTurnMarked = null;

function traceTurn(turn) {
  if (lastTurnMarked === turn) return;
  lastTurnMarked = turn;
  const mark = document.createElement('div');
  mark.className = 'turnmark';
  mark.textContent = `model round ${turn}`;
  el.trace.appendChild(mark);
}

function traceCall(name, args) {
  const entry = document.createElement('div');
  entry.className = 'entry';
  entry.dataset.open = 'false';
  entry.innerHTML = `
    <div class="head"><span class="arrow">→</span><span class="name">${escapeHtml(name)}</span>
    <span class="args">${escapeHtml(args)}</span></div>
    <pre>waiting…</pre>`;
  entry.querySelector('.head').addEventListener('click', () => {
    entry.dataset.open = entry.dataset.open === 'true' ? 'false' : 'true';
  });
  el.trace.appendChild(entry);
  el.trace.scrollTop = el.trace.scrollHeight;
  return entry;
}

function traceResult(entry, ok, result) {
  if (!entry) return;
  entry.classList.add(ok ? 'ok' : 'fail');
  entry.querySelector('.arrow').textContent = ok ? '←' : '✗';
  entry.querySelector('pre').textContent = JSON.stringify(result, null, 2);
  // A failure is the interesting case, so open it without being asked.
  if (!ok) entry.dataset.open = 'true';
  el.trace.scrollTop = el.trace.scrollHeight;
}

function traceEmpty() {
  el.trace.innerHTML = '<div class="trace-empty">No calls yet. Ask about the catalogue and they will appear here.</div>';
  lastTurnMarked = null;
}

// ---------------------------------------------------------------------------
// Cart badge — read straight from the database, never from the conversation
// ---------------------------------------------------------------------------

function refreshCart() {
  if (!context) return;
  try {
    const cart = viewCart(context.db, { session_id: context.session_id });
    el.cart.textContent = cart.item_count === 0
      ? 'Cart empty'
      : `Cart: ${cart.item_count} item${cart.item_count === 1 ? '' : 's'} · ${cart.total_display}`;
  } catch {
    el.cart.textContent = '';
  }
}

// ---------------------------------------------------------------------------
// Turn handling
// ---------------------------------------------------------------------------

async function send(text) {
  if (busy || !text.trim()) return;
  busy = true;
  el.send.disabled = true;
  el.messages.querySelector('.welcome')?.remove();

  addMessage('user', text);
  const thinking = addThinking();
  el.status.textContent = 'thinking…';

  const pending = new Map();

  try {
    const { reply, history: next } = await runTurn({
      history,
      userText: text,
      context,
      token: localStorage.getItem(STORE.token),
      model: el.model.value,
      onEvent: (e) => {
        if (e.type === 'model_request') traceTurn(e.turn);
        if (e.type === 'tool_call') {
          el.status.textContent = `${e.name}…`;
          pending.set(`${e.turn}:${e.name}`, traceCall(e.name, e.arguments));
        }
        if (e.type === 'tool_result') {
          traceResult(pending.get(`${e.turn}:${e.name}`), e.ok, e.result);
          pending.delete(`${e.turn}:${e.name}`);
        }
      },
    });

    history = next;
    thinking.remove();
    addMessage('assistant', reply || '(empty reply)');
  } catch (err) {
    thinking.remove();
    const message = err instanceof InferenceError
      ? `Inference failed: ${err.message}`
      : `Something went wrong: ${err.message}`;
    addMessage('assistant', message, { error: true });
    // A bad or spent token is worth sending the visitor back to the gate.
    if (err instanceof InferenceError && [401, 403].includes(err.status)) {
      localStorage.removeItem(STORE.token);
      showGate(true);
    }
  } finally {
    busy = false;
    el.send.disabled = false;
    el.status.textContent = '';
    refreshCart();
  }
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

function showGate(show) {
  el.gate.hidden = !show;
  el.composer.hidden = show;
  if (!show) el.input.focus();
}

function initModels() {
  for (const m of MODELS) {
    const opt = document.createElement('option');
    opt.value = m.id;
    opt.textContent = m.label;
    el.model.appendChild(opt);
  }
  el.model.value = localStorage.getItem(STORE.model) ?? DEFAULT_MODEL;
  el.model.addEventListener('change', () => localStorage.setItem(STORE.model, el.model.value));
}

function initComposer() {
  el.input.addEventListener('input', () => {
    el.input.style.height = 'auto';
    el.input.style.height = `${Math.min(el.input.scrollHeight, 160)}px`;
  });
  el.input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      el.composer.requestSubmit();
    }
  });
  el.composer.addEventListener('submit', (e) => {
    e.preventDefault();
    const text = el.input.value;
    el.input.value = '';
    el.input.style.height = 'auto';
    send(text);
  });
}

function initControls() {
  el.traceToggle.addEventListener('click', () => {
    const on = el.traceToggle.getAttribute('aria-pressed') === 'true';
    el.traceToggle.setAttribute('aria-pressed', String(!on));
    document.querySelector('main').classList.toggle('no-trace', on);
  });

  el.traceClear.addEventListener('click', traceEmpty);

  el.reset.addEventListener('click', async () => {
    if (!confirm('Rebuild the shop from schema.sql and seed.sql? Your cart and orders will be discarded.')) return;
    await context?.db.reset?.();
    localStorage.removeItem(STORE.session);
    location.reload();
  });

  el.tokenForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const value = el.token.value.trim();
    if (!value) return;
    localStorage.setItem(STORE.token, value);
    el.token.value = '';
    showGate(false);
  });
}

async function main() {
  initModels();
  initComposer();
  initControls();
  traceEmpty();
  welcome();

  el.status.textContent = 'loading the catalogue…';
  try {
    const db = await openDatabase({ base: '.' });
    context = { db, session_id: sessionId() };
    el.status.textContent = '';
  } catch (err) {
    el.status.textContent = '';
    addMessage('assistant', `The catalogue could not be loaded: ${err.message}`, { error: true });
    return;
  }

  refreshCart();
  showGate(!localStorage.getItem(STORE.token));
}

main();
