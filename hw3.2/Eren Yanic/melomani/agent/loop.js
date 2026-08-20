// The agent loop.
//
// Native tool calling only: the tool schemas go up in the `tools` array, the
// provider hands back `message.tool_calls`, the router executes them, and the
// results go back as `role: "tool"` messages. No prompt-injected protocol, no
// text parsing — every model offered by the UI was checked to return real
// tool_calls before it was listed.
//
// Written against fetch and plain objects so the identical file runs in Node
// (scripts/demo.mjs, tests) and in the browser (web/app.js).

import { TOOL_SCHEMAS } from './schemas.js';
import { routeToolCall } from './router.js';
import { buildMessages } from './prompts.js';

export const ENDPOINT = 'https://router.huggingface.co/v1/chat/completions';

// Each entry is pinned to a provider that was verified to return tool_calls.
// A bare model id resolves against whichever providers the caller's account has
// enabled, which fails for most tokens — hence the explicit `:provider` suffix.
export const MODELS = [
  { id: 'Qwen/Qwen2.5-7B-Instruct:featherless-ai', label: 'Qwen2.5 7B Instruct' },
  { id: 'meta-llama/Llama-3.3-70B-Instruct:groq', label: 'Llama 3.3 70B' },
  { id: 'Qwen/Qwen2.5-72B-Instruct:novita', label: 'Qwen2.5 72B Instruct' },
  { id: 'Qwen/Qwen3-32B:featherless-ai', label: 'Qwen3 32B' },
];

export const DEFAULT_MODEL = MODELS[0].id;

/** Raised for provider-level failures so callers can show something useful. */
export class InferenceError extends Error {
  constructor(message, { status = null, body = null } = {}) {
    super(message);
    this.name = 'InferenceError';
    this.status = status;
    this.body = body;
  }
}

async function callModel({ model, messages, token, signal }) {
  let res;
  try {
    res = await fetch(ENDPOINT, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model,
        messages,
        tools: TOOL_SCHEMAS,
        tool_choice: 'auto',
        temperature: 0.3,
        max_tokens: 800,
      }),
      signal,
    });
  } catch (err) {
    if (err.name === 'AbortError') throw err;
    throw new InferenceError(`Could not reach the inference router: ${err.message}`);
  }

  const text = await res.text();
  let data;
  try {
    data = JSON.parse(text);
  } catch {
    throw new InferenceError(`The provider returned a response that is not JSON (HTTP ${res.status}).`, {
      status: res.status, body: text.slice(0, 400),
    });
  }

  if (!res.ok || data.error) {
    const detail = typeof data.error === 'string' ? data.error : data.error?.message ?? `HTTP ${res.status}`;
    const hint = res.status === 401 ? ' Check that the Hugging Face token is valid.'
      : res.status === 402 ? ' The token has no inference credit left for this month.'
        : res.status === 429 ? ' The provider is rate-limiting; wait a moment and retry.'
          : '';
    throw new InferenceError(detail + hint, { status: res.status, body: data });
  }

  const message = data.choices?.[0]?.message;
  if (!message) {
    throw new InferenceError('The provider returned no message.', { status: res.status, body: data });
  }
  return message;
}

// Qwen3 emits chain-of-thought in <think> blocks; a missing opening tag is
// common enough that both forms have to be handled.
function stripReasoning(content) {
  if (!content) return content;
  return content
    .replace(/<think>[\s\S]*?<\/think>/g, '')
    .replace(/^[\s\S]*?<\/think>/, '')
    .trim();
}

/**
 * Run one customer turn to completion.
 *
 * @param {object}   o
 * @param {Array}    o.history   prior messages (no system message)
 * @param {string}   o.userText  what the customer just said
 * @param {object}   o.context   { db, session_id } — passed to every tool
 * @param {string}   o.token     Hugging Face token
 * @param {string}   o.model
 * @param {number}   o.maxTurns  cap on model round-trips
 * @param {Function} o.onEvent   receives trace events as they happen
 * @param {AbortSignal} o.signal
 *
 * @returns {Promise<{ reply: string, history: Array, trace: Array }>}
 */
export async function runTurn({
  history = [],
  userText,
  context,
  token,
  model = DEFAULT_MODEL,
  maxTurns = 6,
  onEvent = () => {},
  signal,
}) {
  const messages = [...history, { role: 'user', content: userText }];
  const trace = [];

  // Marks the customer-turn boundary. tools/cart.js uses it to refuse a
  // checkout that would complete without the customer having answered.
  context.turnId = (context.turnId ?? 0) + 1;

  const emit = (event) => {
    trace.push(event);
    onEvent(event);
  };

  for (let turn = 1; turn <= maxTurns; turn++) {
    emit({ type: 'model_request', turn, model });

    const message = await callModel({
      model, messages: buildMessages(messages), token, signal,
    });

    const toolCalls = message.tool_calls ?? [];

    // The assistant turn must be recorded verbatim, tool_calls included — the
    // provider rejects tool results that answer a call it cannot see.
    messages.push({
      role: 'assistant',
      content: message.content ?? '',
      ...(toolCalls.length ? { tool_calls: toolCalls } : {}),
    });

    if (toolCalls.length === 0) {
      const reply = stripReasoning(message.content) || '';
      emit({ type: 'final', turn, reply });
      return { reply, history: messages, trace };
    }

    for (const call of toolCalls) {
      const name = call.function?.name ?? '(unnamed)';
      const rawArgs = call.function?.arguments ?? '{}';
      emit({ type: 'tool_call', turn, name, arguments: rawArgs });

      const result = routeToolCall(name, rawArgs, context);
      emit({ type: 'tool_result', turn, name, ok: result.ok !== false, result });

      messages.push({
        role: 'tool',
        tool_call_id: call.id ?? `${name}-${turn}`,
        name,
        content: JSON.stringify(result),
      });
    }
  }

  // The model kept calling tools without concluding. Say so rather than
  // presenting a half-finished exchange as an answer.
  const reply = 'I could not finish that request — too many tool steps without reaching an answer. Could you narrow it down?';
  emit({ type: 'exhausted', turn: maxTurns, reply });
  return { reply, history: messages, trace };
}
