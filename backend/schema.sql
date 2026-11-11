-- Thomas Transfer database schema (SQLite).
-- Run automatically by db.init_db(); safe to execute more than once.

CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  first_name    TEXT    NOT NULL,
  last_name     TEXT    NOT NULL,
  email         TEXT    NOT NULL UNIQUE COLLATE NOCASE,
  phone         TEXT    NOT NULL DEFAULT '',
  password_hash TEXT    NOT NULL,
  is_admin      INTEGER NOT NULL DEFAULT 0,
  active        INTEGER NOT NULL DEFAULT 1,
  created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cars (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  name        TEXT    NOT NULL,
  type        TEXT    NOT NULL,
  description TEXT    NOT NULL DEFAULT '',
  image       TEXT    NOT NULL DEFAULT '',
  capacity    INTEGER NOT NULL DEFAULT 4,
  price       TEXT    NOT NULL DEFAULT '',
  week        TEXT    NOT NULL DEFAULT '',
  specs       TEXT    NOT NULL DEFAULT '',
  status      TEXT    NOT NULL DEFAULT 'available'
                      CHECK (status IN ('available', 'booked', 'maintenance')),
  created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bookings (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  car_id     INTEGER NOT NULL REFERENCES cars(id),
  pickup     TEXT    NOT NULL,
  dropoff    TEXT    NOT NULL,
  trip_at    TEXT    NOT NULL,
  passengers INTEGER NOT NULL,
  notes      TEXT    NOT NULL DEFAULT '',
  status     TEXT    NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending', 'confirmed', 'completed', 'cancelled')),
  paid_amount REAL   NOT NULL DEFAULT 0,
  paid_method TEXT   NOT NULL DEFAULT '',
  paid_at     TEXT   NOT NULL DEFAULT '',
  created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings(user_id);
CREATE INDEX IF NOT EXISTS idx_bookings_car  ON bookings(car_id);

CREATE TABLE IF NOT EXISTS comments (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
  name       TEXT    NOT NULL,
  rating     INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
  text       TEXT    NOT NULL,
  handled    INTEGER NOT NULL DEFAULT 0,
  created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS messages (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  name       TEXT    NOT NULL,
  email      TEXT    NOT NULL,
  phone      TEXT    NOT NULL DEFAULT '',
  service    TEXT    NOT NULL DEFAULT '',
  message    TEXT    NOT NULL,
  handled    INTEGER NOT NULL DEFAULT 0,
  created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS fares (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  key       TEXT    NOT NULL UNIQUE COLLATE NOCASE,
  tag       TEXT    NOT NULL DEFAULT '',
  name      TEXT    NOT NULL,
  amount    REAL    NOT NULL CHECK (amount > 0),
  currency  TEXT    NOT NULL DEFAULT 'RWF' CHECK (currency IN ('RWF', 'USD')),
  note      TEXT    NOT NULL DEFAULT '',
  flw_link  TEXT    NOT NULL DEFAULT '',
  active    INTEGER NOT NULL DEFAULT 1,
  created_at TEXT   NOT NULL DEFAULT (datetime('now'))
);
