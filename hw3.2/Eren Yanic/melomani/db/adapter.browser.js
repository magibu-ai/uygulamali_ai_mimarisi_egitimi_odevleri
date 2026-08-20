// Browser adapter — real SQLite compiled to WebAssembly (sql.js), persisted to
// IndexedDB between visits.
//
// This is the same SQLite engine the Node adapter uses, executing the same
// schema.sql and seed.sql. It exposes the identical all/run/transaction
// contract, so db/repository.js is unchanged between the two.
//
// The database is per-browser: nothing is shared with other visitors, and
// nothing leaves the machine.

const IDB_NAME = 'melomani';
const IDB_STORE = 'sqlite';
const IDB_KEY = 'db';
const IDB_VERSION_KEY = 'seed_version';

// Bump whenever schema.sql or seed.sql changes. A returning visitor holds a
// snapshot of the *old* catalogue in IndexedDB, and without this stamp they
// would keep browsing it indefinitely — the shop would silently not stock
// records the deployed seed says it does.
const SEED_VERSION = '2026-08-03-metal-rock';

function idb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(IDB_NAME, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(IDB_STORE);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function idbGet(key) {
  try {
    const conn = await idb();
    return await new Promise((resolve, reject) => {
      const req = conn.transaction(IDB_STORE, 'readonly').objectStore(IDB_STORE).get(key);
      req.onsuccess = () => resolve(req.result ?? null);
      req.onerror = () => reject(req.error);
    });
  } catch {
    return null; // private browsing, storage denied — fall back to a fresh DB
  }
}

/** Load the snapshot, but only if it was built from the current seed. */
async function idbLoad() {
  const version = await idbGet(IDB_VERSION_KEY);
  if (version !== SEED_VERSION) return null;
  return idbGet(IDB_KEY);
}

async function idbSave(bytes) {
  try {
    const conn = await idb();
    await new Promise((resolve, reject) => {
      const tx = conn.transaction(IDB_STORE, 'readwrite');
      const store = tx.objectStore(IDB_STORE);
      store.put(bytes, IDB_KEY);
      store.put(SEED_VERSION, IDB_VERSION_KEY);
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
    });
  } catch {
    /* persistence is a convenience, not a requirement */
  }
}

/**
 * Wraps a sql.js Database in the adapter contract.
 *
 * Exported so the SQL can be exercised under Node — sql.js runs there too, and
 * the schema, the ON CONFLICT upsert and the getRowsModified() semantics the
 * stock guard depends on are all worth testing without a browser.
 */
export class BrowserAdapter {
  #db;
  #depth = 0;
  #saveTimer = null;

  constructor(db) {
    this.#db = db;
  }

  all(sql, params = []) {
    const stmt = this.#db.prepare(sql);
    try {
      stmt.bind(params);
      const rows = [];
      while (stmt.step()) rows.push(stmt.getAsObject());
      return rows;
    } finally {
      stmt.free();
    }
  }

  run(sql, params = []) {
    this.#db.run(sql, params);
    const changes = this.#db.getRowsModified();
    const lastInsertRowid = this.#db.exec('SELECT last_insert_rowid() AS id')[0]?.values[0][0] ?? 0;
    this.#scheduleSave();
    return { changes, lastInsertRowid };
  }

  transaction(fn) {
    if (this.#depth > 0) return fn();
    this.#depth++;
    this.#db.run('BEGIN');
    try {
      const out = fn();
      this.#db.run('COMMIT');
      return out;
    } catch (err) {
      this.#db.run('ROLLBACK');
      throw err;
    } finally {
      this.#depth--;
      this.#scheduleSave();
    }
  }

  /** Serialise the whole database — this is what IndexedDB stores. */
  export() {
    return this.#db.export();
  }

  // Exporting the whole database on every statement would be wasteful; a short
  // debounce collapses a checkout's dozen writes into one snapshot.
  #scheduleSave() {
    if (this.#depth > 0) return; // mid-transaction state is not worth persisting
    clearTimeout(this.#saveTimer);
    this.#saveTimer = setTimeout(() => idbSave(this.#db.export()), 250);
  }

  /** Drop the stored database and rebuild from schema + seed. */
  async reset() {
    const conn = await idb().catch(() => null);
    if (conn) {
      await new Promise((resolve) => {
        const tx = conn.transaction(IDB_STORE, 'readwrite');
        const store = tx.objectStore(IDB_STORE);
        store.delete(IDB_KEY);
        store.delete(IDB_VERSION_KEY);
        tx.oncomplete = resolve;
        tx.onerror = resolve;
      });
    }
  }
}

/**
 * Load sql.js, then either restore the saved database or build a new one from
 * db/schema.sql + db/seed.sql — the same files the Node adapter reads.
 *
 * @param {{ force?: boolean, base?: string }} opts
 */
export async function openDatabase({ force = false, base = '.' } = {}) {
  // sql-wasm.js is a classic script that defines a global `initSqlJs`.
  if (typeof globalThis.initSqlJs !== 'function') {
    await new Promise((resolve, reject) => {
      const el = document.createElement('script');
      el.src = `${base}/web/vendor/sql-wasm.js`;
      el.onload = resolve;
      el.onerror = () => reject(new Error('Could not load sql-wasm.js'));
      document.head.appendChild(el);
    });
  }

  const SQL = await globalThis.initSqlJs({
    locateFile: (file) => `${base}/web/vendor/${file}`,
  });

  const saved = force ? null : await idbLoad();
  if (saved) {
    try {
      return new BrowserAdapter(new SQL.Database(new Uint8Array(saved)));
    } catch {
      /* corrupt snapshot — fall through and rebuild */
    }
  }

  const [schema, seed] = await Promise.all([
    fetch(`${base}/db/schema.sql`).then((r) => r.text()),
    fetch(`${base}/db/seed.sql`).then((r) => r.text()),
  ]);

  const db = new SQL.Database();
  db.run(schema);
  db.run(seed);

  const adapter = new BrowserAdapter(db);
  await idbSave(db.export());
  return adapter;
}
