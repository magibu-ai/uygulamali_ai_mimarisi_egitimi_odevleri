// Repository tests — real SQLite, no model, no browser.
//
// Every case here runs against an in-memory database built from the same
// schema.sql and seed.sql the Space ships.

import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { openDatabase } from '../db/adapter.node.js';
import * as repo from '../db/repository.js';

function fresh() {
  return openDatabase(':memory:');
}

describe('seed data', () => {
  test('catalogue is populated and internally consistent', () => {
    const db = fresh();
    assert.equal(db.all('SELECT count(*) AS n FROM albums')[0].n, 90);
    assert.equal(db.all('SELECT count(*) AS n FROM artists')[0].n, 83);

    // No album may reference a missing artist, and no track a missing album.
    assert.equal(
      db.all('SELECT count(*) AS n FROM albums a LEFT JOIN artists ar ON ar.id = a.artist_id WHERE ar.id IS NULL')[0].n,
      0,
    );
    assert.equal(
      db.all('SELECT count(*) AS n FROM tracks t LEFT JOIN albums a ON a.id = t.album_id WHERE a.id IS NULL')[0].n,
      0,
    );
    // Every album carries at least one tag, or the recommender cannot see it.
    assert.equal(
      db.all('SELECT count(*) AS n FROM albums a WHERE NOT EXISTS (SELECT 1 FROM album_tags t WHERE t.album_id = a.id)')[0].n,
      0,
    );
  });
});

describe('the metal and rock expansion', () => {
  test('every metal subgenre is stocked and reachable by one "metal" search', () => {
    const db = fresh();
    const found = new Set(
      repo.searchAlbums(db, { genre: 'metal', limit: 25 }).results.map((a) => a.genre),
    );
    // Partial matching is what makes a single "metal" query cover the family.
    for (const g of ['thrash-metal', 'death-metal', 'black-metal', 'progressive-metal']) {
      assert.ok(
        db.all('SELECT count(*) AS n FROM albums WHERE genre = ?', [g])[0].n > 0,
        `${g} is not stocked`,
      );
    }
    assert.ok(found.size >= 4, `one "metal" search reached only ${found.size} subgenres`);
    assert.ok([...found].every((g) => g.includes('metal')));
  });

  test('the same holds for the rock family', () => {
    const db = fresh();
    const genres = repo.searchAlbums(db, { genre: 'rock', limit: 25 }).results.map((a) => a.genre);
    assert.ok(genres.every((g) => g.includes('rock')));
    assert.ok(new Set(genres).size >= 3);
  });

  test('every newly added tag is shared by enough albums to score', () => {
    // A tag on a single album contributes nothing to the recommender, so the
    // metal vocabulary has to be genuinely reused.
    const db = fresh();
    for (const tag of ['heavy', 'fast', 'technical', 'epic', 'raw', 'progressive',
      'anthemic', 'occult', 'blues-based']) {
      const n = db.all('SELECT count(*) AS n FROM album_tags WHERE tag = ?', [tag])[0].n;
      assert.ok(n >= 3, `tag "${tag}" is on only ${n} album(s)`);
    }
  });

  test('a metal listener gets metal back, not an incidental tag match', () => {
    const db = fresh();
    const r = repo.recommendAlbums(db, { liked_albums: ['Master of Puppets'], limit: 5 });
    assert.ok(r.count > 0);
    assert.ok(!r.results.some((a) => a.title === 'Master of Puppets'));
    assert.ok(
      r.results.filter((a) => a.genre.includes('metal')).length >= 3,
      `only ${r.results.filter((a) => a.genre.includes('metal')).length} of 5 were metal`,
    );
  });

  test('black metal recommends black metal, not just any metal', () => {
    const db = fresh();
    const r = repo.recommendAlbums(db, { liked_artists: ['Darkthrone'], limit: 4 });
    assert.equal(r.results[0].genre, 'black-metal');
  });

  test('Turkish and casual metal words reach the English tags', () => {
    const db = fresh();
    for (const mood of ['ağır', 'hızlı', 'brutal', 'şeytani', 'destansı']) {
      const r = repo.recommendAlbums(db, { moods: [mood], limit: 3 });
      assert.ok(r.count > 0, `"${mood}" matched nothing`);
    }
    // "aggressive" now points at heavy rather than noise.
    const agg = repo.recommendAlbums(db, { moods: ['aggressive'], limit: 5 });
    assert.ok(agg.results.some((a) => a.genre.includes('metal')));
  });

  test('spaced and Turkish genre spellings normalise onto stored values', () => {
    const db = fresh();
    for (const [given, expected] of [
      ['black metal', 'black-metal'], ['prog metal', 'progressive-metal'],
      ['ağır metal', 'heavy-metal'], ['classic rock', 'classic-rock'],
      ['psikedelik', 'psych-rock'],
    ]) {
      const r = repo.recommendAlbums(db, { genres: [given], limit: 3 });
      assert.ok(r.count > 0, `genre "${given}" matched nothing`);
      assert.ok(
        r.results.some((a) => a.genre === expected),
        `"${given}" did not reach ${expected}`,
      );
    }
  });

  test('the older catalogue is undisturbed by the expansion', () => {
    const db = fresh();
    // Existing ids must stay put — tests and traces reference them.
    assert.equal(repo.getAlbumDetails(db, { album_id: 1 }).title, 'Dummy');
    assert.equal(repo.getAlbumDetails(db, { album_id: 2 }).title, 'Mezzanine');
    assert.equal(repo.getAlbumDetails(db, { album_id: 20 }).title, 'Kind of Blue');

    const r = repo.recommendAlbums(db, { liked_artists: ['Portishead'], moods: ['melancholic'], limit: 5 });
    assert.equal(r.results[0].genre, 'trip-hop');
    assert.ok(r.results.some((a) => a.title === 'Mezzanine'));
  });
});

describe('searchAlbums', () => {
  test('finds by free text across title, artist and genre', () => {
    const db = fresh();
    assert.ok(repo.searchAlbums(db, { query: 'Portishead' }).results.some((r) => r.title === 'Dummy'));
    assert.ok(repo.searchAlbums(db, { query: 'Dummy' }).results.some((r) => r.artist === 'Portishead'));
    assert.ok(repo.searchAlbums(db, { query: 'post-punk' }).count > 0);
  });

  test('applies year, price and stock filters', () => {
    const db = fresh();
    const r = repo.searchAlbums(db, { year_from: 1959, year_to: 1965, limit: 25 });
    assert.ok(r.count > 0);
    assert.ok(r.results.every((a) => a.year >= 1959 && a.year <= 1965));

    const cheap = repo.searchAlbums(db, { max_price_try: 300, limit: 25 });
    assert.ok(cheap.results.every((a) => a.price_try <= 300));
  });

  test('an empty result carries an explicit instruction, not a bare list', () => {
    const db = fresh();
    const r = repo.searchAlbums(db, { query: 'Nonexistent Record By Nobody' });
    assert.equal(r.count, 0);
    assert.deepEqual(r.results, []);
    assert.match(r.message, /not in the catalogue/i);
  });

  test('limit is clamped so the model cannot flood its own context', () => {
    const db = fresh();
    assert.ok(repo.searchAlbums(db, { limit: 9999 }).count <= 25);
    assert.equal(repo.searchAlbums(db, { limit: 0 }).count, 1);
  });
});

describe('getAlbumDetails', () => {
  test('returns tracklist and tags for a real album', () => {
    const db = fresh();
    const d = repo.getAlbumDetails(db, { album_id: 1 });
    assert.equal(d.ok, true);
    assert.equal(d.title, 'Dummy');
    assert.equal(d.track_count, 11);
    assert.equal(d.tracks[0].title, 'Mysterons');
    assert.match(d.tracks[0].duration, /^\d+:\d{2}$/);
    assert.ok(d.tags.includes('melancholic'));
  });

  test('an unknown id is a structured error, never an invented album', () => {
    const db = fresh();
    const d = repo.getAlbumDetails(db, { album_id: 99999 });
    assert.equal(d.ok, false);
    assert.equal(d.error, 'ALBUM_NOT_FOUND');
  });
});

describe('recommendAlbums', () => {
  test('a seed album yields same-genre neighbours with a data-derived reason', () => {
    const db = fresh();
    const r = repo.recommendAlbums(db, { liked_albums: ['Dummy'], limit: 5 });
    assert.ok(r.count > 0);
    // The seed itself must not be recommended back.
    assert.ok(!r.results.some((a) => a.title === 'Dummy'));
    // Top hit should share Dummy's genre.
    assert.equal(r.results[0].genre, 'trip-hop');
    // Every result explains itself from stored columns.
    for (const a of r.results) {
      assert.ok(a.why.length > 0);
      assert.ok(a.score > 0);
    }
  });

  test('scores are ordered descending', () => {
    const db = fresh();
    const r = repo.recommendAlbums(db, { genres: ['jazz'], moods: ['improvisation'], limit: 6 });
    const scores = r.results.map((a) => a.score);
    assert.deepEqual(scores, [...scores].sort((a, b) => b - a));
  });

  test('moods alone are enough to recommend', () => {
    const db = fresh();
    const r = repo.recommendAlbums(db, { moods: ['nocturnal', 'melancholic'], limit: 4 });
    assert.ok(r.count > 0);
    assert.ok(r.results.every((a) => /shares/.test(a.why)));
  });

  test('an artist the shop does not stock refuses rather than improvising', () => {
    const db = fresh();
    const r = repo.recommendAlbums(db, { liked_artists: ['Some Band That Does Not Exist'] });
    assert.equal(r.count, 0);
    assert.match(r.message, /none of the named artists or albums are in this catalogue/i);
  });

  test('no taste signal at all asks for one', () => {
    const db = fresh();
    const r = repo.recommendAlbums(db, {});
    assert.equal(r.count, 0);
    assert.match(r.message, /no taste signal/i);
  });

  test('out-of-stock albums are not recommended by default', () => {
    const db = fresh();
    db.run('UPDATE albums SET stock = 0 WHERE genre = ?', ['trip-hop']);
    const r = repo.recommendAlbums(db, { genres: ['trip-hop'], limit: 5 });
    assert.ok(r.results.every((a) => a.stock > 0));
  });
});

describe('cart', () => {
  const S = 'test-session';

  test('adding accumulates quantity and totals in kurus-exact arithmetic', () => {
    const db = fresh();
    repo.addToCart(db, { session_id: S, album_id: 20, quantity: 2 });
    const r = repo.addToCart(db, { session_id: S, album_id: 20, quantity: 1 });
    assert.equal(r.ok, true);
    assert.equal(r.cart.item_count, 3);
    assert.equal(r.cart.total_try, 329 * 3);
    assert.equal(r.cart.total_display, '987,00 ₺');
  });

  test('an id that does not exist cannot enter the cart', () => {
    const db = fresh();
    const r = repo.addToCart(db, { session_id: S, album_id: 4242, quantity: 1 });
    assert.equal(r.error, 'ALBUM_NOT_FOUND');
    assert.equal(repo.viewCart(db, { session_id: S }).item_count, 0);
  });

  test('the cart cannot exceed stock, counting what is already in it', () => {
    const db = fresh();
    const stock = db.all('SELECT stock FROM albums WHERE id = 5')[0].stock;
    repo.addToCart(db, { session_id: S, album_id: 5, quantity: stock });
    const r = repo.addToCart(db, { session_id: S, album_id: 5, quantity: 1 });
    assert.equal(r.error, 'INSUFFICIENT_STOCK');
    assert.equal(r.stock, stock);
  });

  test('quantity must be a positive whole number', () => {
    const db = fresh();
    assert.equal(repo.addToCart(db, { session_id: S, album_id: 1, quantity: 0 }).error, 'INVALID_QUANTITY');
    assert.equal(repo.addToCart(db, { session_id: S, album_id: 1, quantity: -3 }).error, 'INVALID_QUANTITY');
  });

  test('carts are isolated by session', () => {
    const db = fresh();
    repo.addToCart(db, { session_id: 'alice', album_id: 1, quantity: 1 });
    assert.equal(repo.viewCart(db, { session_id: 'bob' }).item_count, 0);
  });
});

describe('checkout', () => {
  const S = 'checkout-session';

  test('places an order, deducts stock and empties the cart', () => {
    const db = fresh();
    const before = db.all('SELECT stock FROM albums WHERE id = 15')[0].stock;
    repo.addToCart(db, { session_id: S, album_id: 15, quantity: 2 });

    const o = repo.checkout(db, { session_id: S, customer_name: 'Eren' });
    assert.equal(o.ok, true);
    assert.ok(o.order_id > 0);
    assert.equal(o.total_try, 459 * 2);

    assert.equal(db.all('SELECT stock FROM albums WHERE id = 15')[0].stock, before - 2);
    assert.equal(repo.viewCart(db, { session_id: S }).item_count, 0);
  });

  test('the stored total is recomputed from the order rows, not passed in', () => {
    const db = fresh();
    repo.addToCart(db, { session_id: S, album_id: 20, quantity: 2 });
    repo.addToCart(db, { session_id: S, album_id: 21, quantity: 1 });
    const o = repo.checkout(db, { session_id: S, customer_name: 'Eren' });

    const stored = db.all('SELECT total_kurus FROM orders WHERE id = ?', [o.order_id])[0].total_kurus;
    const summed = db.all(
      'SELECT sum(quantity * unit_price_kurus) AS t FROM order_items WHERE order_id = ?', [o.order_id],
    )[0].t;
    assert.equal(stored, summed);
    assert.equal(stored, 32900 * 2 + 34900);
  });

  test('an empty cart is refused', () => {
    const db = fresh();
    assert.equal(repo.checkout(db, { session_id: 'nobody', customer_name: 'X' }).error, 'EMPTY_CART');
  });

  test('a missing customer name is refused', () => {
    const db = fresh();
    repo.addToCart(db, { session_id: S, album_id: 1, quantity: 1 });
    assert.equal(repo.checkout(db, { session_id: S, customer_name: '  ' }).error, 'CUSTOMER_NAME_REQUIRED');
  });

  test('stock sold out between browsing and checkout rolls the whole order back', () => {
    const db = fresh();
    repo.addToCart(db, { session_id: S, album_id: 20, quantity: 2 });
    repo.addToCart(db, { session_id: S, album_id: 8, quantity: 2 });

    // Someone else takes the last copies of album 8 in the meantime.
    db.run('UPDATE albums SET stock = 0 WHERE id = 8');
    const stock20 = db.all('SELECT stock FROM albums WHERE id = 20')[0].stock;

    const r = repo.checkout(db, { session_id: S, customer_name: 'Eren' });
    assert.equal(r.error, 'INSUFFICIENT_STOCK');

    // The successful line must have been rolled back too — no partial order.
    assert.equal(db.all('SELECT stock FROM albums WHERE id = 20')[0].stock, stock20);
    assert.equal(db.all('SELECT count(*) AS n FROM orders')[0].n, 0);
    assert.equal(db.all('SELECT count(*) AS n FROM order_items')[0].n, 0);
    // And the cart survives, so the customer can adjust it.
    assert.ok(repo.viewCart(db, { session_id: S }).item_count > 0);
  });

  test('order prices are frozen at checkout time', () => {
    const db = fresh();
    repo.addToCart(db, { session_id: S, album_id: 1, quantity: 1 });
    const o = repo.checkout(db, { session_id: S, customer_name: 'Eren' });

    db.run('UPDATE albums SET price_kurus = 99900 WHERE id = 1');
    const status = repo.checkOrderStatus(db, { session_id: S, order_id: o.order_id });
    assert.equal(status.total_display, '349,00 ₺');
  });
});

describe('checkOrderStatus', () => {
  const S = 'status-session';

  test('reports a stage derived from elapsed time', () => {
    const db = fresh();
    repo.addToCart(db, { session_id: S, album_id: 1, quantity: 1 });
    const o = repo.checkout(db, { session_id: S, customer_name: 'Eren' });

    assert.equal(repo.checkOrderStatus(db, { session_id: S, order_id: o.order_id }).status, 'preparing');

    // Backdate the order and the stage advances without any state change.
    db.run('UPDATE orders SET placed_at = ? WHERE id = ?',
      [new Date(Date.now() - 700_000).toISOString(), o.order_id]);
    assert.equal(repo.checkOrderStatus(db, { session_id: S, order_id: o.order_id }).status, 'delivered');
  });

  test('an order from another session is not readable', () => {
    const db = fresh();
    repo.addToCart(db, { session_id: S, album_id: 1, quantity: 1 });
    const o = repo.checkout(db, { session_id: S, customer_name: 'Eren' });
    assert.equal(repo.checkOrderStatus(db, { session_id: 'intruder', order_id: o.order_id }).error, 'ORDER_NOT_FOUND');
  });

  test('an unknown order id is a structured error', () => {
    const db = fresh();
    assert.equal(repo.checkOrderStatus(db, { session_id: S, order_id: 12345 }).error, 'ORDER_NOT_FOUND');
  });
});
