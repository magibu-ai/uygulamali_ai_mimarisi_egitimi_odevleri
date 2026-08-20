-- melomani — schema
--
-- One file, two runtimes: executed by node:sqlite locally and by sql.js in the
-- browser. Nothing here is adapter-specific.
--
-- Money is stored in kurus (integer TRY * 100). Floating point currency in a
-- shop that computes order totals is a bug waiting for a rounding error.

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS cart_items;
DROP TABLE IF EXISTS tracks;
DROP TABLE IF EXISTS album_tags;
DROP TABLE IF EXISTS albums;
DROP TABLE IF EXISTS artists;

CREATE TABLE artists (
  id          INTEGER PRIMARY KEY,
  name        TEXT    NOT NULL UNIQUE,
  country     TEXT,
  formed_year INTEGER
);

CREATE TABLE albums (
  id          INTEGER PRIMARY KEY,
  artist_id   INTEGER NOT NULL REFERENCES artists(id),
  title       TEXT    NOT NULL,
  year        INTEGER NOT NULL,
  genre       TEXT    NOT NULL,
  label       TEXT,
  format      TEXT    NOT NULL DEFAULT 'CD',
  price_kurus INTEGER NOT NULL CHECK (price_kurus > 0),
  stock       INTEGER NOT NULL DEFAULT 0 CHECK (stock >= 0),
  UNIQUE (artist_id, title)
);

-- Free-form descriptors (mood, style, scene). The recommender scores overlap
-- across this table, so a tag vocabulary that is reused across albums matters
-- more than a tag that is precise but unique.
CREATE TABLE album_tags (
  album_id INTEGER NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
  tag      TEXT    NOT NULL,
  PRIMARY KEY (album_id, tag)
);

CREATE TABLE tracks (
  id           INTEGER PRIMARY KEY,
  album_id     INTEGER NOT NULL REFERENCES albums(id) ON DELETE CASCADE,
  position     INTEGER NOT NULL,
  title        TEXT    NOT NULL,
  duration_sec INTEGER,
  UNIQUE (album_id, position)
);

-- Carts are keyed by a browser-generated session id, so two people browsing the
-- Space at the same time never share a basket. There is no cart row as such:
-- a cart is just the set of cart_items carrying a session_id.
CREATE TABLE cart_items (
  session_id TEXT    NOT NULL,
  album_id   INTEGER NOT NULL REFERENCES albums(id),
  quantity   INTEGER NOT NULL CHECK (quantity > 0),
  added_at   TEXT    NOT NULL,
  PRIMARY KEY (session_id, album_id)
);

CREATE TABLE orders (
  id            INTEGER PRIMARY KEY,
  session_id    TEXT    NOT NULL,
  customer_name TEXT    NOT NULL,
  total_kurus   INTEGER NOT NULL CHECK (total_kurus >= 0),
  placed_at     TEXT    NOT NULL
);

-- unit_price_kurus is captured at checkout on purpose: an order must not change
-- value when the catalogue is repriced afterwards.
CREATE TABLE order_items (
  order_id         INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  album_id         INTEGER NOT NULL REFERENCES albums(id),
  quantity         INTEGER NOT NULL CHECK (quantity > 0),
  unit_price_kurus INTEGER NOT NULL,
  PRIMARY KEY (order_id, album_id)
);

CREATE INDEX idx_albums_artist ON albums(artist_id);
CREATE INDEX idx_albums_genre  ON albums(genre);
CREATE INDEX idx_albums_year   ON albums(year);
CREATE INDEX idx_tags_tag      ON album_tags(tag);
CREATE INDEX idx_tracks_album  ON tracks(album_id);
CREATE INDEX idx_orders_session ON orders(session_id);
