// Router tests — the boundary where a model's output becomes a database call.
//
// These cases are drawn from how models actually misbehave: numbers sent as
// strings, a bare string where a list is declared, arguments delivered as a
// JSON string, required fields omitted, and tool names that do not exist.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { openDatabase } from '../db/adapter.node.js';
import { routeToolCall, prepareArguments } from '../agent/router.js';
import { TOOL_NAMES, TOOL_SCHEMAS } from '../agent/schemas.js';

const ctx = () => ({ db: openDatabase(':memory:'), session_id: 'router-test' });

describe('tool schemas', () => {
  test('every declared tool has a handler and a well-formed schema', () => {
    assert.equal(TOOL_NAMES.length, 6);
    for (const t of TOOL_SCHEMAS) {
      assert.equal(t.type, 'function');
      assert.ok(t.function.description.length > 20);
      assert.equal(t.function.parameters.type, 'object');
      // A handler must exist, or the model can call something that does nothing.
      const r = routeToolCall(t.function.name, '{}', ctx());
      assert.notEqual(r.error, 'UNKNOWN_TOOL');
    }
  });

  test('no write tool accepts a free-text album name', () => {
    // The guarantee that an invented title cannot become an order.
    for (const name of ['add_to_cart']) {
      const props = TOOL_SCHEMAS.find((t) => t.function.name === name).function.parameters.properties;
      assert.equal(props.album_id.type, 'integer');
      assert.ok(!('title' in props));
      assert.ok(!('album_title' in props));
    }
  });
});

describe('argument coercion', () => {
  test('numeric strings become numbers', () => {
    const { args } = prepareArguments('add_to_cart', { album_id: '20', quantity: '3' });
    assert.equal(args.album_id, 20);
    assert.equal(args.quantity, 3);
  });

  test('a bare string is accepted where an array is declared', () => {
    const { args } = prepareArguments('recommend_albums', { moods: 'nocturnal' });
    assert.deepEqual(args.moods, ['nocturnal']);
  });

  test('arguments delivered as a JSON string are parsed', () => {
    const { args } = prepareArguments('get_album_details', '{"album_id": 7}');
    assert.equal(args.album_id, 7);
  });

  test('an empty argument string is an empty object, not a failure', () => {
    const { args, error } = prepareArguments('search_albums', '');
    assert.equal(error, undefined);
    assert.deepEqual(args, {});
  });

  test('booleans arrive as strings and are coerced', () => {
    const { args } = prepareArguments('search_albums', { in_stock_only: 'true' });
    assert.equal(args.in_stock_only, true);
  });

  test('a non-integer where an integer is declared is rejected', () => {
    const { error } = prepareArguments('add_to_cart', { album_id: 'Dummy' });
    assert.equal(error.error, 'INVALID_ARGUMENTS');
    assert.match(error.message, /whole number/);
  });

  test('malformed JSON is reported back rather than thrown', () => {
    const { error } = prepareArguments('add_to_cart', '{album_id: 20,}');
    assert.equal(error.error, 'INVALID_ARGUMENTS');
  });

  test('missing required arguments name what is missing', () => {
    const { error } = prepareArguments('add_to_cart', {});
    assert.equal(error.error, 'MISSING_ARGUMENTS');
    assert.match(error.message, /album_id/);
  });

  test('undeclared properties are dropped, not passed through', () => {
    const { args } = prepareArguments('search_albums', { query: 'jazz', session_id: 'someone-else', db: 'x' });
    assert.deepEqual(Object.keys(args), ['query']);
  });
});

describe('routing', () => {
  test('an unknown tool name lists the real ones', () => {
    const r = routeToolCall('order_pizza', '{}', ctx());
    assert.equal(r.error, 'UNKNOWN_TOOL');
    assert.match(r.message, /search_albums/);
  });

  test('session context is injected, never taken from the model', () => {
    const c = ctx();
    routeToolCall('add_to_cart', { album_id: 1, quantity: 1 }, c);
    // The model tried to name a different session; it must have been ignored.
    const r = routeToolCall('add_to_cart', { album_id: 2, quantity: 1, session_id: 'victim' }, c);
    assert.equal(r.ok, true);
    assert.equal(r.cart.item_count, 2);
    assert.equal(c.db.all('SELECT count(*) AS n FROM cart_items WHERE session_id = ?', ['victim'])[0].n, 0);
  });

  test('a full search-then-buy-then-check round trip routes correctly', () => {
    const c = { ...ctx(), turnId: 1 };
    const found = routeToolCall('search_albums', { query: 'Kind of Blue' }, c);
    const id = found.results[0].album_id;

    assert.equal(routeToolCall('add_to_cart', { album_id: String(id), quantity: '1' }, c).ok, true);

    // Turn 1 previews only.
    assert.equal(routeToolCall('checkout', { customer_name: 'Eren' }, c).error, 'CONFIRMATION_REQUIRED');

    // The customer answers; a new turn commits.
    c.turnId = 2;
    const order = routeToolCall('checkout', { customer_name: 'Eren' }, c);
    assert.equal(order.ok, true);

    const status = routeToolCall('check_order_status', { order_id: order.order_id }, c);
    assert.equal(status.ok, true);
    assert.equal(status.items[0].album_id, id);
  });

  test('checkout cannot complete inside a single customer turn', () => {
    const c = { ...ctx(), turnId: 7 };
    routeToolCall('add_to_cart', { album_id: 1, quantity: 1 }, c);

    // However many times the model calls it within one turn, nothing is bought.
    for (let i = 0; i < 4; i++) {
      const r = routeToolCall('checkout', { customer_name: 'Eren' }, c);
      assert.equal(r.error, 'CONFIRMATION_REQUIRED');
      assert.ok(r.preview.total_display.length > 0);
    }
    assert.equal(c.db.all('SELECT count(*) AS n FROM orders')[0].n, 0);
    // The stock is untouched too.
    assert.equal(c.db.all('SELECT stock FROM albums WHERE id = 1')[0].stock, 6);
  });

  test('the preview shows the real basket, and an empty cart is refused outright', () => {
    const c = { ...ctx(), turnId: 1 };
    assert.equal(routeToolCall('checkout', { customer_name: 'Eren' }, c).error, 'EMPTY_CART');

    routeToolCall('add_to_cart', { album_id: 20, quantity: 2 }, c);
    const r = routeToolCall('checkout', { customer_name: 'Eren' }, c);
    assert.equal(r.preview.item_count, 2);
    assert.equal(r.preview.total_display, '658,00 ₺');
    assert.equal(r.preview.customer_name, 'Eren');
  });

  test('the gate rearms after a completed order', () => {
    const c = { ...ctx(), turnId: 1 };
    routeToolCall('add_to_cart', { album_id: 1, quantity: 1 }, c);
    routeToolCall('checkout', { customer_name: 'Eren' }, c);
    c.turnId = 2;
    assert.equal(routeToolCall('checkout', { customer_name: 'Eren' }, c).ok, true);

    // A second order must be previewed again, not waved through.
    routeToolCall('add_to_cart', { album_id: 2, quantity: 1 }, c);
    c.turnId = 3;
    assert.equal(routeToolCall('checkout', { customer_name: 'Eren' }, c).error, 'CONFIRMATION_REQUIRED');
    assert.equal(c.db.all('SELECT count(*) AS n FROM orders')[0].n, 1);
  });

  test('a tool that throws becomes a readable error, not a crash', () => {
    const broken = { db: null, session_id: 's' };
    const r = routeToolCall('search_albums', { query: 'x' }, broken);
    assert.equal(r.error, 'TOOL_FAILED');
    assert.equal(r.ok, false);
  });
});
