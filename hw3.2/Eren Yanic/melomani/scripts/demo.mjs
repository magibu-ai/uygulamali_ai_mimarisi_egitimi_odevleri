#!/usr/bin/env node
//
// Terminal runner. Same agent loop, same router, same repository as the web
// interface — the only difference is a file-backed SQLite database instead of
// one in WebAssembly, and stdout instead of a trace panel.
//
//   HF_TOKEN=hf_... node scripts/demo.mjs
//   HF_TOKEN=hf_... node scripts/demo.mjs "Portishead severim, ne önerirsin?"
//   HF_TOKEN=hf_... node scripts/demo.mjs --script     # scripted end-to-end run
//   node scripts/demo.mjs --db-only                    # tools only, no model
//
// --db-only exercises the tools directly and needs no token or network, which
// is useful when inference credit has run out.

import { createInterface } from 'node:readline/promises';
import { stdin, stdout, argv, env, exit } from 'node:process';
import { openDatabase } from '../db/adapter.node.js';
import { routeToolCall } from '../agent/router.js';
import { runTurn, MODELS, DEFAULT_MODEL, InferenceError } from '../agent/loop.js';

const C = {
  reset: '\x1b[0m', dim: '\x1b[2m', bold: '\x1b[1m',
  cyan: '\x1b[36m', green: '\x1b[32m', yellow: '\x1b[33m',
  red: '\x1b[31m', magenta: '\x1b[35m', blue: '\x1b[34m',
};

const DB_PATH = env.MELOMANI_DB ?? 'melomani.db';
const SESSION = `cli-${Date.now()}`;

function truncate(s, n) {
  const str = typeof s === 'string' ? s : JSON.stringify(s);
  return str.length > n ? `${str.slice(0, n)}…` : str;
}

/** Print one trace event. This is the tool-call log the assignment asks for. */
function printEvent(e) {
  switch (e.type) {
    case 'model_request':
      console.log(`${C.dim}[turn ${e.turn}] → model ${e.model}${C.reset}`);
      break;
    case 'tool_call':
      console.log(`${C.yellow}  →  ${C.bold}${e.name}${C.reset}${C.yellow}(${truncate(e.arguments, 160)})${C.reset}`);
      break;
    case 'tool_result': {
      const colour = e.ok ? C.green : C.red;
      const mark = e.ok ? '←' : '✗';
      console.log(`${colour}  ${mark}  ${truncate(e.result, 320)}${C.reset}`);
      break;
    }
    case 'final':
      console.log(`${C.dim}[turn ${e.turn}] final${C.reset}`);
      break;
    case 'exhausted':
      console.log(`${C.red}[turn ${e.turn}] tool budget exhausted${C.reset}`);
      break;
  }
}

// ---------------------------------------------------------------------------
// --db-only: drive the tools directly, no model in the loop
// ---------------------------------------------------------------------------

function dbOnly(db) {
  const context = { db, session_id: SESSION, turnId: 1 };
  // turn: which customer turn the call belongs to. checkout is gated on this,
  // so the two checkout calls below sit in different turns on purpose.
  const calls = [
    [1, 'search_albums', { genre: 'trip-hop', in_stock_only: true, limit: 3 }],
    [1, 'recommend_albums', { liked_albums: ['Dummy'], moods: ['hüzünlü'], limit: 3 }],
    // "metal" matches every subgenre, and "ağır" normalises onto the heavy tag.
    [1, 'search_albums', { genre: 'metal', in_stock_only: true, limit: 4 }],
    [1, 'recommend_albums', { liked_albums: ['Reign in Blood'], moods: ['ağır'], limit: 3 }],
    [1, 'get_album_details', { album_id: 2 }],
    [1, 'add_to_cart', { album_id: 2, quantity: 1 }],
    [1, 'add_to_cart', { album_id: 9999, quantity: 1 }],
    [1, 'checkout', { customer_name: 'Eren' }],   // previews only
    [2, 'checkout', { customer_name: 'Eren' }],   // commits
  ];

  console.log(`${C.bold}melomani — tool layer, no model${C.reset}  ${C.dim}db: ${DB_PATH}${C.reset}\n`);
  let lastOrder = null;
  for (const [turn, name, args] of calls) {
    context.turnId = turn;
    console.log(`${C.dim}[turn ${turn}]${C.reset} ${C.yellow}→  ${C.bold}${name}${C.reset}${C.yellow}(${JSON.stringify(args)})${C.reset}`);
    const result = routeToolCall(name, args, context);
    const colour = result.ok === false ? C.red : C.green;
    console.log(`${colour}  ${result.ok === false ? '✗' : '←'}  ${truncate(result, 400)}${C.reset}\n`);
    if (result.order_id) lastOrder = result.order_id;
  }
  if (lastOrder) {
    console.log(`${C.dim}[turn 2]${C.reset} ${C.yellow}→  ${C.bold}check_order_status${C.reset}${C.yellow}({"order_id":${lastOrder}})${C.reset}`);
    console.log(`${C.green}  ←  ${truncate(routeToolCall('check_order_status', { order_id: lastOrder }, context), 400)}${C.reset}`);
  }
}

// ---------------------------------------------------------------------------
// Model-driven runs
// ---------------------------------------------------------------------------

// `context` is created once per session and threaded through every turn: it
// carries turnId and the checkout gate, both of which are meaningless if a
// fresh object is handed to each turn.
async function runOne({ context, token, model, history, text }) {
  console.log(`\n${C.cyan}${C.bold}customer:${C.reset} ${text}`);
  try {
    const { reply, history: next } = await runTurn({
      history,
      userText: text,
      context,
      token,
      model,
      onEvent: printEvent,
    });
    console.log(`${C.magenta}${C.bold}melomani:${C.reset} ${reply}\n`);
    return next;
  } catch (err) {
    if (err instanceof InferenceError) {
      console.error(`${C.red}inference failed: ${err.message}${C.reset}`);
      if (err.status) console.error(`${C.dim}HTTP ${err.status}${C.reset}`);
      return history;
    }
    throw err;
  }
}

// A full browse → recommend → cart → order → status path in one run.
const SCRIPT = [
  'Merhaba, Portishead severim. Benzer, hüzünlü bir şey önerir misin?',
  'Mezzanine kulağa iyi geliyor, içinde hangi şarkılar var?',
  'Tamam, onu sepete ekle.',
  'Siparişi ver, adım Eren.',
  'Evet, onaylıyorum.',
];

async function main() {
  const args = argv.slice(2);
  const db = openDatabase(DB_PATH);

  if (args.includes('--db-only')) {
    dbOnly(db);
    return;
  }

  const token = env.HF_TOKEN ?? env.HUGGINGFACE_TOKEN;
  if (!token) {
    console.error(`${C.red}HF_TOKEN is not set.${C.reset}`);
    console.error('Get one at https://huggingface.co/settings/tokens (inference permission), then:');
    console.error('  HF_TOKEN=hf_... node scripts/demo.mjs');
    console.error(`\nOr run the tool layer with no model and no token:\n  node scripts/demo.mjs --db-only`);
    exit(1);
  }

  const modelArg = args.find((a) => a.startsWith('--model='));
  const model = modelArg ? modelArg.split('=')[1] : DEFAULT_MODEL;

  const context = { db, session_id: SESSION };

  console.log(`${C.bold}melomani${C.reset}  ${C.dim}model: ${model}  db: ${DB_PATH}  session: ${SESSION}${C.reset}`);
  console.log(`${C.dim}models available: ${MODELS.map((m) => m.id).join(', ')}${C.reset}`);

  let history = [];

  if (args.includes('--script')) {
    for (const line of SCRIPT) {
      history = await runOne({ context, token, model, history, text: line });
    }
    return;
  }

  const oneShot = args.find((a) => !a.startsWith('--'));
  if (oneShot) {
    await runOne({ context, token, model, history, text: oneShot });
    return;
  }

  const rl = createInterface({ input: stdin, output: stdout });
  console.log(`${C.dim}Type a message, or Ctrl-C to leave.${C.reset}`);
  for (;;) {
    const text = (await rl.question(`\n${C.cyan}> ${C.reset}`)).trim();
    if (!text) continue;
    if (['exit', 'quit', 'çık'].includes(text.toLowerCase())) break;
    history = await runOne({ context, token, model, history, text });
  }
  rl.close();
}

main().catch((err) => {
  console.error(`${C.red}${err.stack ?? err.message}${C.reset}`);
  exit(1);
});
