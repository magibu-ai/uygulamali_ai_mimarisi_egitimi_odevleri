// Node adapter — real, file-backed SQLite via node:sqlite (built into Node 22+,
// no dependency to install).
//
// Used by the test suite and by scripts/demo.mjs. The browser adapter exposes
// the same three methods, so db/repository.js never learns which one it has.

import { DatabaseSync } from 'node:sqlite';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const HERE = dirname(fileURLToPath(import.meta.url));

/**
 * The adapter contract, shared with adapter.browser.js:
 *   all(sql, params)  -> array of row objects
 *   run(sql, params)  -> { changes, lastInsertRowid }
 *   transaction(fn)   -> runs fn, commits on return, rolls back on throw
 */
class NodeAdapter {
  #db;
  #depth = 0; // guards against a nested transaction issuing a second BEGIN

  constructor(db) {
    this.#db = db;
  }

  all(sql, params = []) {
    return this.#db.prepare(sql).all(...params);
  }

  run(sql, params = []) {
    const r = this.#db.prepare(sql).run(...params);
    return { changes: Number(r.changes), lastInsertRowid: Number(r.lastInsertRowid) };
  }

  transaction(fn) {
    if (this.#depth > 0) return fn(); // already inside one; join it
    this.#depth++;
    this.#db.exec('BEGIN');
    try {
      const out = fn();
      this.#db.exec('COMMIT');
      return out;
    } catch (err) {
      this.#db.exec('ROLLBACK');
      throw err;
    } finally {
      this.#depth--;
    }
  }

  close() {
    this.#db.close();
  }
}

/**
 * Open a database and, when it is empty, build it from schema.sql + seed.sql.
 *
 * @param {string} path  file path, or ':memory:' for tests
 * @param {boolean} force  rebuild even if tables already exist
 */
export function openDatabase(path = ':memory:', { force = false } = {}) {
  const db = new DatabaseSync(path);
  db.exec('PRAGMA foreign_keys = ON');

  const seeded = db
    .prepare("SELECT count(*) AS n FROM sqlite_master WHERE type='table' AND name='albums'")
    .get().n > 0;

  if (!seeded || force) {
    db.exec(readFileSync(join(HERE, 'schema.sql'), 'utf8'));
    db.exec(readFileSync(join(HERE, 'seed.sql'), 'utf8'));
  }

  return new NodeAdapter(db);
}
