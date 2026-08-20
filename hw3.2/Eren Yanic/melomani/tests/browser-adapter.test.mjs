// The browser adapter's SQL, exercised under Node.
//
// sql.js is WebAssembly and runs in Node as happily as in a page, so the half
// of adapter.browser.js that could silently break — whether SQLite-in-WASM
// accepts this project's SQL — is testable here. IndexedDB persistence and the
// dynamic <script> load are browser-only and are not covered.
//
// This matters because the repository is shared: if sql.js disagreed with
// node:sqlite on the stock-guard semantics, the Space would oversell while
// every other test stayed green.

import { test, describe, before } from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import { BrowserAdapter, openDatabase } from '../db/adapter.browser.js';
import * as repo from '../db/repository.js';

const require = createRequire(import.meta.url);
const HERE = dirname(fileURLToPath(import.meta.url));
const DB_DIR = join(HERE, '..', 'db');

let SQL;

before(async () => {
  const initSqlJs = require('../web/vendor/sql-wasm.js');
  SQL = await initSqlJs({
    locateFile: (f) => join(HERE, '..', 'web', 'vendor', f),
  });
});

/** Build a database the way the browser does: run schema.sql, then seed.sql. */
function fresh() {
  const db = new SQL.Database();
  db.run(readFileSync(join(DB_DIR, 'schema.sql'), 'utf8'));
  db.run(readFileSync(join(DB_DIR, 'seed.sql'), 'utf8'));
  return new BrowserAdapter(db);
}

describe('sql.js accepts the project SQL', () => {
  test('schema and seed load as multi-statement scripts', () => {
    const db = fresh();
    assert.equal(db.all('SELECT count(*) AS n FROM albums')[0].n, 90);
    assert.equal(db.all('SELECT count(*) AS n FROM tracks')[0].n, 879);
  });

  test('Turkish text in the seed survives intact', () => {
    const db = fresh();
    const rows = db.all('SELECT name FROM artists WHERE name LIKE ?', ['%Man%']);
    assert.ok(rows.some((r) => r.name === 'Barış Manço'));
    assert.equal(db.all('SELECT title FROM albums WHERE id = 40')[0].title, 'Elektronik Türküler');
  });

  test('the ON CONFLICT upsert behaves as it does under node:sqlite', () => {
    const db = fresh();
    repo.addToCart(db, { session_id: 's', album_id: 20, quantity: 2 });
    repo.addToCart(db, { session_id: 's', album_id: 20, quantity: 1 });
    const rows = db.all('SELECT quantity FROM cart_items WHERE session_id = ? AND album_id = 20', ['s']);
    assert.equal(rows.length, 1);
    assert.equal(rows[0].quantity, 3);
  });

  test('getRowsModified reports 0 when the stock guard blocks an update', () => {
    // The rollback in checkout() hinges on this exact semantic.
    const db = fresh();
    const r = db.run('UPDATE albums SET stock = stock - ? WHERE id = ? AND stock >= ?', [999, 1, 999]);
    assert.equal(r.changes, 0);
    const ok = db.run('UPDATE albums SET stock = stock - ? WHERE id = ? AND stock >= ?', [1, 1, 1]);
    assert.equal(ok.changes, 1);
  });

  test('lastInsertRowid comes back from an insert', () => {
    const db = fresh();
    const r = db.run('INSERT INTO orders (session_id, customer_name, total_kurus, placed_at) VALUES (?,?,?,?)',
      ['s', 'Eren', 100, new Date().toISOString()]);
    assert.ok(r.lastInsertRowid > 0);
  });
});

describe('the repository produces identical results on sql.js', () => {
  test('search, details and recommendation all work unchanged', () => {
    const db = fresh();

    const s = repo.searchAlbums(db, { genre: 'trip-hop', in_stock_only: true, limit: 5 });
    assert.ok(s.count > 0);
    assert.ok(s.results.every((a) => a.genre === 'trip-hop'));

    const d = repo.getAlbumDetails(db, { album_id: 1 });
    assert.equal(d.title, 'Dummy');
    assert.equal(d.track_count, 11);

    // The recommender's nested scoring subqueries are the most complex SQL in
    // the project; this is where a WASM/native divergence would show.
    const r = repo.recommendAlbums(db, { liked_artists: ['Portishead'], moods: ['melancholic'], limit: 5 });
    assert.ok(r.count > 0);
    assert.equal(r.results[0].genre, 'trip-hop');
    assert.ok(r.results.every((a) => a.score > 0 && a.why.length > 0));
    assert.ok(r.results.some((a) => a.title === 'Mezzanine'));
  });

  test('vocabulary normalisation works the same way', () => {
    const db = fresh();
    const r = repo.recommendAlbums(db, { moods: ['hüzünlü'], limit: 3 });
    assert.ok(r.count > 0);
  });

  test('a checkout transaction commits and deducts stock', () => {
    const db = fresh();
    const before = db.all('SELECT stock FROM albums WHERE id = 15')[0].stock;
    repo.addToCart(db, { session_id: 's', album_id: 15, quantity: 2 });

    const o = repo.checkout(db, { session_id: 's', customer_name: 'Eren' });
    assert.equal(o.ok, true);
    assert.equal(db.all('SELECT stock FROM albums WHERE id = 15')[0].stock, before - 2);
    assert.equal(repo.viewCart(db, { session_id: 's' }).item_count, 0);
  });

  test('a failed checkout rolls the whole transaction back', () => {
    const db = fresh();
    repo.addToCart(db, { session_id: 's', album_id: 20, quantity: 2 });
    repo.addToCart(db, { session_id: 's', album_id: 8, quantity: 2 });
    db.run('UPDATE albums SET stock = 0 WHERE id = 8');
    const stock20 = db.all('SELECT stock FROM albums WHERE id = 20')[0].stock;

    const r = repo.checkout(db, { session_id: 's', customer_name: 'Eren' });
    assert.equal(r.error, 'INSUFFICIENT_STOCK');
    assert.equal(db.all('SELECT stock FROM albums WHERE id = 20')[0].stock, stock20);
    assert.equal(db.all('SELECT count(*) AS n FROM orders')[0].n, 0);
  });

  test('export produces a byte array that reopens as the same database', () => {
    // This is what IndexedDB persistence stores and restores.
    const db = fresh();
    repo.addToCart(db, { session_id: 's', album_id: 1, quantity: 1 });
    const o = repo.checkout(db, { session_id: 's', customer_name: 'Eren' });

    const bytes = db.export();
    assert.ok(bytes.length > 0);

    const reopened = new BrowserAdapter(new SQL.Database(bytes));
    const status = repo.checkOrderStatus(reopened, { session_id: 's', order_id: o.order_id });
    assert.equal(status.ok, true);
    assert.equal(status.total_display, '349,00 ₺');
  });
});

describe('openDatabase, the function the page actually calls', () => {
  // openDatabase reaches for three browser globals. Two are shimmed here so the
  // build-from-SQL path can be exercised; indexedDB is deliberately left absent,
  // which is also the real behaviour under a storage-denied browser and must
  // degrade to a working in-memory database rather than throw.
  test('fetches schema and seed, then builds a queryable catalogue', async () => {
    const initSqlJs = require('../web/vendor/sql-wasm.js');
    globalThis.initSqlJs = (opts) => initSqlJs({
      ...opts,
      locateFile: (f) => join(HERE, '..', 'web', 'vendor', f),
    });

    const realFetch = globalThis.fetch;
    globalThis.fetch = async (url) => {
      const rel = String(url).replace(/^\.\//, '');
      return { text: async () => readFileSync(join(HERE, '..', rel), 'utf8') };
    };

    try {
      const db = await openDatabase({ base: '.' });
      assert.equal(db.all('SELECT count(*) AS n FROM albums')[0].n, 90);

      // And the full stack runs on it, exactly as the page would.
      const rec = repo.recommendAlbums(db, { moods: ['nocturnal'], limit: 3 });
      assert.ok(rec.count > 0);
      const add = repo.addToCart(db, { session_id: 'page', album_id: rec.results[0].album_id, quantity: 1 });
      assert.equal(add.ok, true);
    } finally {
      globalThis.fetch = realFetch;
      delete globalThis.initSqlJs;
    }
  });
});

// A minimal IndexedDB good enough for the two calls adapter.browser.js makes.
// Real IDB fires its callbacks asynchronously, so this does too — a synchronous
// fake would pass while the real thing deadlocked.
function fakeIndexedDB() {
  const data = new Map();
  const later = (fn) => setTimeout(fn, 0);
  const request = (compute) => {
    const req = {};
    later(() => { req.result = compute(); req.onsuccess?.(); });
    return req;
  };
  const api = {
    _data: data,
    open() {
      const req = {};
      const db = {
        createObjectStore() {},
        transaction() {
          const tx = {};
          tx.objectStore = () => ({
            get: (k) => request(() => data.get(k)),
            put: (v, k) => request(() => { data.set(k, v); }),
            delete: (k) => request(() => { data.delete(k); }),
          });
          later(() => tx.oncomplete?.());
          return tx;
        },
      };
      later(() => { req.result = db; req.onupgradeneeded?.(); req.onsuccess?.(); });
      return req;
    },
  };
  return api;
}

function installBrowserGlobals() {
  const initSqlJs = require('../web/vendor/sql-wasm.js');
  const saved = { fetch: globalThis.fetch, idb: globalThis.indexedDB };

  globalThis.initSqlJs = (opts) => initSqlJs({
    ...opts, locateFile: (f) => join(HERE, '..', 'web', 'vendor', f),
  });
  globalThis.fetch = async (url) => ({
    text: async () => readFileSync(join(HERE, '..', String(url).replace(/^\.\//, '')), 'utf8'),
  });
  const idb = fakeIndexedDB();
  globalThis.indexedDB = idb;

  return {
    idb,
    restore() {
      globalThis.fetch = saved.fetch;
      globalThis.indexedDB = saved.idb;
      delete globalThis.initSqlJs;
    },
  };
}

describe('the seed version stamp', () => {
  test('a snapshot from an older seed is discarded rather than served', async () => {
    const env = installBrowserGlobals();
    try {
      // First visit: builds from SQL and stores a stamped snapshot.
      const first = await openDatabase({ base: '.' });
      first.run("INSERT INTO cart_items (session_id, album_id, quantity, added_at) VALUES ('v','1',1,'now')");
      await new Promise((r) => setTimeout(r, 400)); // let the debounced save land

      assert.ok(env.idb._data.has('db'), 'no snapshot was persisted');
      assert.ok(env.idb._data.has('seed_version'), 'no version was stamped');

      // Returning visitor on the same seed: the snapshot is reused, so the row
      // written above survives.
      const second = await openDatabase({ base: '.' });
      assert.equal(second.all('SELECT count(*) AS n FROM cart_items')[0].n, 1);

      // Now the deployed seed changes underneath them.
      env.idb._data.set('seed_version', 'an-older-release');
      const third = await openDatabase({ base: '.' });

      // Rebuilt from SQL: the stale cart is gone and the catalogue is current.
      assert.equal(third.all('SELECT count(*) AS n FROM cart_items')[0].n, 0);
      assert.equal(third.all('SELECT count(*) AS n FROM albums')[0].n, 90);
    } finally {
      env.restore();
    }
  });

  test('force rebuilds even when the stamp matches', async () => {
    const env = installBrowserGlobals();
    try {
      const db = await openDatabase({ base: '.' });
      db.run("INSERT INTO cart_items (session_id, album_id, quantity, added_at) VALUES ('v','1',1,'now')");
      await new Promise((r) => setTimeout(r, 400));

      const forced = await openDatabase({ base: '.', force: true });
      assert.equal(forced.all('SELECT count(*) AS n FROM cart_items')[0].n, 0);
    } finally {
      env.restore();
    }
  });
});
