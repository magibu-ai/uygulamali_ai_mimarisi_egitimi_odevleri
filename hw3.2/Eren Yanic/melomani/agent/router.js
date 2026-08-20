// Function routing.
//
// Between "the model emitted a tool call" and "a SQL statement runs" there is
// exactly one place where the call is checked, and this is it:
//
//   1. Is this a tool that exists?
//   2. Do the arguments parse, and can they be coerced to the declared types?
//      (Models routinely send "3" for an integer, or a bare string where an
//      array is declared. Untreated, "3" + 1 becomes "31".)
//   3. Are the required arguments present?
//   4. Dispatch, and convert any thrown error into a result the model can read.
//
// Every failure returns a structured object rather than throwing, so the loop
// can hand it back as a tool result and let the model correct itself.

import { TOOL_SCHEMAS } from './schemas.js';
import { catalogTools } from '../tools/catalog.js';
import { cartTools } from '../tools/cart.js';

const HANDLERS = { ...catalogTools, ...cartTools };

const SCHEMA_BY_NAME = new Map(TOOL_SCHEMAS.map((t) => [t.function.name, t.function.parameters]));

function toolError(code, message, extra = {}) {
  return { ok: false, error: code, message, ...extra };
}

/** Coerce one value to its declared JSON Schema type, or return a type error. */
function coerce(name, value, spec) {
  if (value === null || value === undefined) return { value: undefined };

  switch (spec.type) {
    case 'integer': {
      const n = typeof value === 'string' ? Number(value.trim()) : Number(value);
      if (!Number.isFinite(n) || !Number.isInteger(n)) {
        return { error: `"${name}" must be a whole number, got ${JSON.stringify(value)}.` };
      }
      return { value: n };
    }
    case 'number': {
      const n = typeof value === 'string' ? Number(value.trim().replace(',', '.')) : Number(value);
      if (!Number.isFinite(n)) {
        return { error: `"${name}" must be a number, got ${JSON.stringify(value)}.` };
      }
      return { value: n };
    }
    case 'boolean': {
      if (typeof value === 'boolean') return { value };
      if (value === 'true' || value === 'false') return { value: value === 'true' };
      return { error: `"${name}" must be true or false, got ${JSON.stringify(value)}.` };
    }
    case 'array': {
      // A single string where a list is expected is the common case, not an error.
      const arr = Array.isArray(value) ? value : [value];
      const out = [];
      for (const item of arr) {
        const r = coerce(`${name}[]`, item, spec.items ?? { type: 'string' });
        if (r.error) return r;
        if (r.value !== undefined) out.push(r.value);
      }
      return { value: out };
    }
    case 'string':
    default:
      return { value: typeof value === 'string' ? value : String(value) };
  }
}

/**
 * Validate and normalise the arguments of one tool call.
 * @returns {{ args?: object, error?: object }}
 */
export function prepareArguments(toolName, rawArguments) {
  const schema = SCHEMA_BY_NAME.get(toolName);
  if (!schema) {
    return {
      error: toolError(
        'UNKNOWN_TOOL',
        `There is no tool called "${toolName}". Available tools: ${[...SCHEMA_BY_NAME.keys()].join(', ')}.`,
      ),
    };
  }

  // Providers hand arguments back as a JSON string.
  let parsed = rawArguments;
  if (typeof rawArguments === 'string') {
    if (rawArguments.trim() === '') {
      parsed = {};
    } else {
      try {
        parsed = JSON.parse(rawArguments);
      } catch {
        return {
          error: toolError(
            'INVALID_ARGUMENTS',
            `Arguments for ${toolName} were not valid JSON. Re-issue the call with a valid JSON object.`,
          ),
        };
      }
    }
  }
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) {
    return {
      error: toolError('INVALID_ARGUMENTS', `Arguments for ${toolName} must be a JSON object.`),
    };
  }

  const args = {};
  for (const [key, spec] of Object.entries(schema.properties ?? {})) {
    if (!(key in parsed)) continue;
    const r = coerce(key, parsed[key], spec);
    if (r.error) return { error: toolError('INVALID_ARGUMENTS', r.error) };
    if (r.value !== undefined) args[key] = r.value;
  }

  const missing = (schema.required ?? []).filter((k) => args[k] === undefined);
  if (missing.length) {
    return {
      error: toolError(
        'MISSING_ARGUMENTS',
        `${toolName} requires ${missing.join(', ')}. Obtain the value first — for an album_id, search the catalogue.`,
      ),
    };
  }

  return { args };
}

/**
 * Execute one tool call.
 *
 * @param {string} name        tool name as emitted by the model
 * @param {string|object} rawArguments  arguments as emitted by the model
 * @param {{ db: object, session_id: string }} context  trusted, never model-supplied
 */
export function routeToolCall(name, rawArguments, context) {
  const { args, error } = prepareArguments(name, rawArguments);
  if (error) return error;

  try {
    return HANDLERS[name](args, context);
  } catch (err) {
    // A crash in a tool must not kill the conversation; the model is told what
    // happened and can try something else.
    return toolError('TOOL_FAILED', `${name} failed: ${err.message}`);
  }
}
