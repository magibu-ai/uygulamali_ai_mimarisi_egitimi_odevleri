// melomani — repository
//
// Every SQL statement in the project lives here. The adapter passed in is
// either node:sqlite (local, file-backed) or sql.js (browser); this module
// cannot tell them apart and must never try to.
//
// Two rules that the rest of the codebase leans on:
//   1. Prices and totals are computed here, in SQL, from stored rows. Nothing
//      upstream — least of all the model — recomputes them.
//   2. Failures return structured error objects rather than throwing, so a tool
//      result is always something the model can read and act on.

import { normaliseMood, normaliseGenre } from './vocab.js';

const KURUS = 100;

/** Structured failure. Tools hand these straight back to the model. */
function fail(code, message, extra = {}) {
  return { ok: false, error: code, message, ...extra };
}

function tl(kurus) {
  return Math.round(kurus) / KURUS;
}

/** "349,00 ₺" — formatted once, here, so the model never does arithmetic. */
function money(kurus) {
  return `${tl(kurus).toFixed(2).replace('.', ',')} ₺`;
}

/**
 * Build a parameterised `col IN (?,?,?)` fragment.
 * An empty list yields `0`, a false expression — never the `IN ()` syntax error.
 */
function inClause(col, values) {
  if (!values || values.length === 0) return { sql: '0', params: [] };
  return { sql: `${col} IN (${values.map(() => '?').join(',')})`, params: values };
}

function albumRow(r) {
  return {
    album_id: r.id,
    title: r.title,
    artist: r.artist,
    year: r.year,
    genre: r.genre,
    label: r.label,
    format: r.format,
    price_try: tl(r.price_kurus),
    price_display: money(r.price_kurus),
    stock: r.stock,
  };
}

const SELECT_ALBUM = `
  SELECT a.id, a.title, a.year, a.genre, a.label, a.format, a.price_kurus, a.stock,
         ar.name AS artist
  FROM albums a
  JOIN artists ar ON ar.id = a.artist_id`;

// ---------------------------------------------------------------------------
// Catalogue — reads
// ---------------------------------------------------------------------------

/**
 * Filtered catalogue search. Every filter is optional; with none supplied this
 * returns the head of the catalogue rather than an error, which is what a
 * browsing customer actually wants.
 */
export function searchAlbums(db, {
  query = null, artist = null, genre = null,
  year_from = null, year_to = null, max_price_try = null,
  in_stock_only = false, limit = 10,
} = {}) {
  const where = [];
  const params = [];

  if (query) {
    where.push('(a.title LIKE ? OR ar.name LIKE ? OR a.genre LIKE ?)');
    const like = `%${query}%`;
    params.push(like, like, like);
  }
  if (artist) { where.push('ar.name LIKE ?'); params.push(`%${artist}%`); }
  if (genre) { where.push('a.genre LIKE ?'); params.push(`%${normaliseGenre(genre)}%`); }
  if (year_from != null) { where.push('a.year >= ?'); params.push(year_from); }
  if (year_to != null) { where.push('a.year <= ?'); params.push(year_to); }
  if (max_price_try != null) { where.push('a.price_kurus <= ?'); params.push(Math.round(max_price_try * KURUS)); }
  if (in_stock_only) where.push('a.stock > 0');

  const sql = `${SELECT_ALBUM}
    ${where.length ? `WHERE ${where.join(' AND ')}` : ''}
    ORDER BY a.stock > 0 DESC, a.year DESC, a.id ASC
    LIMIT ?`;

  const rows = db.all(sql, [...params, Math.min(Math.max(limit, 1), 25)]);
  const results = rows.map(albumRow);

  // An empty array is the single most common trigger for a model inventing
  // stock. Say it in words instead.
  if (results.length === 0) {
    return {
      ok: true,
      count: 0,
      results: [],
      message: 'No album in the catalogue matches these filters. Do not suggest titles that are not in the catalogue; offer to relax a filter instead.',
    };
  }
  return { ok: true, count: results.length, results };
}

/** Full record for one album, tracklist included. */
export function getAlbumDetails(db, { album_id }) {
  const row = db.all(`${SELECT_ALBUM} WHERE a.id = ?`, [album_id])[0];
  if (!row) {
    return fail('ALBUM_NOT_FOUND', `No album with id ${album_id} exists in the catalogue.`, { album_id });
  }

  const tags = db.all('SELECT tag FROM album_tags WHERE album_id = ? ORDER BY tag', [album_id])
    .map((t) => t.tag);
  const tracks = db.all(
    'SELECT position, title, duration_sec FROM tracks WHERE album_id = ? ORDER BY position',
    [album_id],
  );
  const artistRow = db.all(
    'SELECT ar.country, ar.formed_year FROM artists ar JOIN albums a ON a.artist_id = ar.id WHERE a.id = ?',
    [album_id],
  )[0];

  return {
    ok: true,
    ...albumRow(row),
    country: artistRow?.country ?? null,
    tags,
    track_count: tracks.length,
    tracks: tracks.map((t) => ({
      position: t.position,
      title: t.title,
      duration: t.duration_sec == null
        ? null
        : `${Math.floor(t.duration_sec / 60)}:${String(t.duration_sec % 60).padStart(2, '0')}`,
    })),
    in_stock: row.stock > 0,
  };
}

/**
 * Taste-based recommendation.
 *
 * The score is computed in SQL over stored tags, genre, artist and release year
 * — the model contributes only the seed preferences. Each result carries a
 * `why` assembled from the columns that actually scored, so the justification
 * shown to the customer is derived data rather than model prose.
 */
export function recommendAlbums(db, {
  liked_artists = [], liked_albums = [], genres = [], moods = [],
  decade = null, limit = 5, in_stock_only = true,
} = {}) {
  // 1. Resolve the seed preferences to concrete catalogue rows.
  const seedIds = new Set();
  const seedArtistIds = new Set();

  for (const name of liked_artists) {
    for (const r of db.all('SELECT id FROM artists WHERE name LIKE ?', [`%${name}%`])) {
      seedArtistIds.add(r.id);
    }
  }
  for (const title of liked_albums) {
    const rows = typeof title === 'number'
      ? db.all('SELECT id, artist_id FROM albums WHERE id = ?', [title])
      : db.all('SELECT id, artist_id FROM albums WHERE title LIKE ?', [`%${title}%`]);
    for (const r of rows) { seedIds.add(r.id); seedArtistIds.add(r.artist_id); }
  }
  // A named artist with no named album still seeds their catalogue entries.
  for (const aid of seedArtistIds) {
    for (const r of db.all('SELECT id FROM albums WHERE artist_id = ?', [aid])) seedIds.add(r.id);
  }

  const unresolved = [...liked_artists, ...liked_albums].length > 0 && seedIds.size === 0;

  // 2. Assemble the taste profile: tags and genres of the seeds, plus whatever
  //    the customer stated outright.
  // Incoming mood and genre words are mapped onto the stored vocabulary first —
  // a model handed "hüzünlü" or "dark" would otherwise score nothing at all.
  const profileTags = new Set(moods.map(normaliseMood));
  const profileGenres = new Set(genres.map(normaliseGenre));
  let yearSum = 0;
  let yearCount = 0;

  if (seedIds.size > 0) {
    const ids = [...seedIds];
    const idIn = inClause('album_id', ids);
    for (const r of db.all(`SELECT DISTINCT tag FROM album_tags WHERE ${idIn.sql}`, idIn.params)) {
      profileTags.add(r.tag);
    }
    const aIn = inClause('id', ids);
    for (const r of db.all(`SELECT genre, year FROM albums WHERE ${aIn.sql}`, aIn.params)) {
      profileGenres.add(r.genre.toLowerCase());
      yearSum += r.year;
      yearCount++;
    }
  }

  if (profileTags.size === 0 && profileGenres.size === 0) {
    return {
      ok: true,
      count: 0,
      results: [],
      message: unresolved
        ? 'None of the named artists or albums are in this catalogue, so no similarity could be computed. Ask the customer for a genre or a mood instead, and do not invent recommendations.'
        : 'No taste signal was supplied. Ask the customer for an artist, album, genre or mood before recommending.',
    };
  }

  const centreYear = yearCount > 0 ? Math.round(yearSum / yearCount)
    : decade != null ? Number(decade) + 5
      : null;

  // 3. Score every candidate in SQL.
  const tagIn = inClause('t.tag', [...profileTags]);
  const genreIn = inClause('lower(a.genre)', [...profileGenres]);
  const artistIn = inClause('a.artist_id', [...seedArtistIds]);
  const excludeIn = inClause('a.id', [...seedIds]);

  const params = [
    ...tagIn.params,
    ...genreIn.params,
    ...artistIn.params,
    centreYear ?? 0, centreYear ?? 0,
    ...excludeIn.params,
  ];

  const sql = `
    SELECT * FROM (
      SELECT scored.*,
             -- Genre outweighs two shared tags on purpose. Tag overlap alone
             -- lets an incidental match ("debut", "sampling") float a hip-hop
             -- record above the trip-hop one the customer actually wants.
             (scored.tag_hits * 3 + scored.genre_hit * 6 + scored.artist_hit * 2 + scored.era_hit * 2) AS score
      FROM (
        SELECT a.id, a.title, a.year, a.genre, a.label, a.format, a.price_kurus, a.stock,
               ar.name AS artist,
               (SELECT count(*) FROM album_tags t WHERE t.album_id = a.id AND ${tagIn.sql}) AS tag_hits,
               (CASE WHEN ${genreIn.sql} THEN 1 ELSE 0 END) AS genre_hit,
               (CASE WHEN ${artistIn.sql} THEN 1 ELSE 0 END) AS artist_hit,
               (CASE WHEN ? != 0 AND abs(a.year - ?) <= 6 THEN 1 ELSE 0 END) AS era_hit
        FROM albums a
        JOIN artists ar ON ar.id = a.artist_id
        WHERE NOT (${excludeIn.sql})
          ${in_stock_only ? 'AND a.stock > 0' : ''}
      ) AS scored
    )
    WHERE score > 0
    ORDER BY score DESC, stock DESC, id ASC
    LIMIT ?`;

  const rows = db.all(sql, [...params, Math.min(Math.max(limit, 1), 10)]);

  if (rows.length === 0) {
    return {
      ok: true,
      count: 0,
      results: [],
      message: 'Nothing in the catalogue scores against that taste profile. Say so plainly and ask for a different direction rather than naming albums the shop does not stock.',
    };
  }

  // 4. Build each `why` from the columns that scored. Data, not prose.
  const ids = rows.map((r) => r.id);
  const idIn = inClause('album_id', ids);
  const tagsByAlbum = new Map(ids.map((id) => [id, []]));
  for (const r of db.all(
    `SELECT album_id, tag FROM album_tags WHERE ${idIn.sql} ORDER BY tag`, idIn.params,
  )) {
    tagsByAlbum.get(r.album_id).push(r.tag);
  }

  const results = rows.map((r) => {
    const shared = tagsByAlbum.get(r.id).filter((t) => profileTags.has(t));
    const reasons = [];
    if (r.genre_hit) reasons.push(`same genre (${r.genre})`);
    if (shared.length) reasons.push(`shares ${shared.slice(0, 3).join(', ')}`);
    if (r.artist_hit) reasons.push('same artist you named');
    if (r.era_hit) reasons.push(`released ${r.year}, close to the era you like`);
    return { ...albumRow(r), score: r.score, why: reasons.join('; ') };
  });

  return { ok: true, count: results.length, results };
}

// ---------------------------------------------------------------------------
// Cart and orders — writes
// ---------------------------------------------------------------------------

function cartState(db, session_id) {
  const rows = db.all(
    `SELECT c.album_id, c.quantity, a.title, a.price_kurus, a.stock, ar.name AS artist
     FROM cart_items c
     JOIN albums a ON a.id = c.album_id
     JOIN artists ar ON ar.id = a.artist_id
     WHERE c.session_id = ?
     ORDER BY c.added_at, c.album_id`,
    [session_id],
  );
  const total = rows.reduce((s, r) => s + r.price_kurus * r.quantity, 0);
  return {
    items: rows.map((r) => ({
      album_id: r.album_id,
      title: r.title,
      artist: r.artist,
      quantity: r.quantity,
      unit_price_display: money(r.price_kurus),
      line_total_display: money(r.price_kurus * r.quantity),
    })),
    item_count: rows.reduce((s, r) => s + r.quantity, 0),
    total_try: tl(total),
    total_display: money(total),
  };
}

/**
 * Add to cart by album_id only — never by title. A title the model invented
 * cannot resolve to an id, so it cannot become a cart line.
 */
export function addToCart(db, { session_id, album_id, quantity = 1 }) {
  if (!Number.isInteger(quantity) || quantity < 1) {
    return fail('INVALID_QUANTITY', `Quantity must be a positive whole number, got ${quantity}.`);
  }

  const album = db.all(
    `SELECT a.id, a.title, a.stock, ar.name AS artist
     FROM albums a JOIN artists ar ON ar.id = a.artist_id WHERE a.id = ?`,
    [album_id],
  )[0];
  if (!album) {
    return fail('ALBUM_NOT_FOUND', `No album with id ${album_id} exists. Search the catalogue for a valid id first.`, { album_id });
  }

  const existing = db.all(
    'SELECT quantity FROM cart_items WHERE session_id = ? AND album_id = ?',
    [session_id, album_id],
  )[0];
  const wanted = (existing?.quantity ?? 0) + quantity;

  if (wanted > album.stock) {
    return fail(
      'INSUFFICIENT_STOCK',
      `Only ${album.stock} copies of "${album.title}" are in stock; the cart would need ${wanted}.`,
      { album_id, title: album.title, stock: album.stock, requested: wanted },
    );
  }

  db.run(
    `INSERT INTO cart_items (session_id, album_id, quantity, added_at)
     VALUES (?, ?, ?, ?)
     ON CONFLICT(session_id, album_id) DO UPDATE SET quantity = ?`,
    [session_id, album_id, wanted, new Date().toISOString(), wanted],
  );

  return {
    ok: true,
    added: { album_id, title: album.title, artist: album.artist, quantity },
    cart: cartState(db, session_id),
  };
}

export function viewCart(db, { session_id }) {
  const cart = cartState(db, session_id);
  if (cart.items.length === 0) {
    return { ok: true, ...cart, message: 'The cart is empty.' };
  }
  return { ok: true, ...cart };
}

/**
 * Turn the cart into an order.
 *
 * Stock is deducted with a `WHERE stock >= quantity` guard inside a single
 * transaction: if any line fails the guard the whole checkout rolls back, so a
 * cart can never oversell. The order total is summed in SQL from the captured
 * unit prices.
 */
export function checkout(db, { session_id, customer_name }) {
  if (!customer_name || !String(customer_name).trim()) {
    return fail('CUSTOMER_NAME_REQUIRED', 'A customer name is required to place the order. Ask the customer for one.');
  }

  const lines = db.all(
    `SELECT c.album_id, c.quantity, a.title, a.price_kurus, a.stock
     FROM cart_items c JOIN albums a ON a.id = c.album_id
     WHERE c.session_id = ? ORDER BY c.album_id`,
    [session_id],
  );
  if (lines.length === 0) {
    return fail('EMPTY_CART', 'The cart is empty, so there is nothing to check out.');
  }

  try {
    return db.transaction(() => {
      for (const line of lines) {
        const res = db.run(
          'UPDATE albums SET stock = stock - ? WHERE id = ? AND stock >= ?',
          [line.quantity, line.album_id, line.quantity],
        );
        if (res.changes === 0) {
          // Someone else bought the last copy between browsing and checkout.
          const err = new Error('oversell');
          err.payload = fail(
            'INSUFFICIENT_STOCK',
            `"${line.title}" no longer has ${line.quantity} copies in stock. The order was not placed and nothing was charged.`,
            { album_id: line.album_id, title: line.title, requested: line.quantity },
          );
          throw err;
        }
      }

      const placed_at = new Date().toISOString();
      const order = db.run(
        'INSERT INTO orders (session_id, customer_name, total_kurus, placed_at) VALUES (?, ?, 0, ?)',
        [session_id, String(customer_name).trim(), placed_at],
      );
      const orderId = order.lastInsertRowid;

      for (const line of lines) {
        db.run(
          `INSERT INTO order_items (order_id, album_id, quantity, unit_price_kurus)
           VALUES (?, ?, ?, ?)`,
          [orderId, line.album_id, line.quantity, line.price_kurus],
        );
      }

      // Total comes out of the order rows themselves.
      const { total } = db.all(
        'SELECT sum(quantity * unit_price_kurus) AS total FROM order_items WHERE order_id = ?',
        [orderId],
      )[0];
      db.run('UPDATE orders SET total_kurus = ? WHERE id = ?', [total, orderId]);
      db.run('DELETE FROM cart_items WHERE session_id = ?', [session_id]);

      return {
        ok: true,
        order_id: orderId,
        customer_name: String(customer_name).trim(),
        placed_at,
        item_count: lines.reduce((s, l) => s + l.quantity, 0),
        total_try: tl(total),
        total_display: money(total),
        items: lines.map((l) => ({
          album_id: l.album_id,
          title: l.title,
          quantity: l.quantity,
          unit_price_display: money(l.price_kurus),
        })),
      };
    });
  } catch (err) {
    if (err.payload) return err.payload;
    throw err;
  }
}

// Fulfilment stages, derived from elapsed time. The scale is compressed so the
// progression is observable during a demo rather than over three days.
const STAGES = [
  { after_sec: 0, status: 'preparing' },
  { after_sec: 60, status: 'packed' },
  { after_sec: 180, status: 'shipped' },
  { after_sec: 600, status: 'delivered' },
];

export function checkOrderStatus(db, { session_id, order_id }) {
  const order = db.all(
    'SELECT id, session_id, customer_name, total_kurus, placed_at FROM orders WHERE id = ?',
    [order_id],
  )[0];

  // Scoping to the session stops one visitor reading another's order.
  if (!order || order.session_id !== session_id) {
    return fail('ORDER_NOT_FOUND', `No order with id ${order_id} was placed in this session.`, { order_id });
  }

  const items = db.all(
    `SELECT oi.album_id, oi.quantity, oi.unit_price_kurus, a.title, ar.name AS artist
     FROM order_items oi
     JOIN albums a ON a.id = oi.album_id
     JOIN artists ar ON ar.id = a.artist_id
     WHERE oi.order_id = ? ORDER BY oi.album_id`,
    [order_id],
  );

  const elapsed = Math.max(0, (Date.now() - Date.parse(order.placed_at)) / 1000);
  const stage = [...STAGES].reverse().find((s) => elapsed >= s.after_sec);

  return {
    ok: true,
    order_id: order.id,
    customer_name: order.customer_name,
    status: stage.status,
    placed_at: order.placed_at,
    elapsed_seconds: Math.round(elapsed),
    total_display: money(order.total_kurus),
    items: items.map((i) => ({
      album_id: i.album_id,
      title: i.title,
      artist: i.artist,
      quantity: i.quantity,
      unit_price_display: money(i.unit_price_kurus),
    })),
  };
}
