-- =============================================================================
-- db/schema.sql
-- Travel Search SQLite Schema
-- =============================================================================
-- Notes:
--   * package_hotel_items stores the package <-> hotel many-to-many link.
--   * All TEXT primary keys use the original system IDs.
--   * FTS5 virtual tables are created for full-text keyword search.
--   * Comma-separated denormalised columns (types, destinations, facilities)
--     are stored as plain TEXT for simplicity; FTS5 searches them naturally.
-- =============================================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;


-- ---------------------------------------------------------------------------
-- Packages
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS packages (
    package_id       INTEGER PRIMARY KEY,
    hash_id          TEXT    NOT NULL UNIQUE,
    title            TEXT    NOT NULL,
    sub_title        TEXT    DEFAULT '',
    duration_days    INTEGER DEFAULT 0,
    short_description TEXT   DEFAULT '',
    description      TEXT    DEFAULT '',
    category         TEXT    DEFAULT '',
    types            TEXT    DEFAULT '',   -- pipe-separated list
    destinations     TEXT    DEFAULT '',   -- pipe-separated list
    is_popular       INTEGER DEFAULT 0,
    is_new           INTEGER DEFAULT 0,
    is_designer      INTEGER DEFAULT 0,
    permalink        TEXT    DEFAULT '',
    status           INTEGER DEFAULT 1,
    created_at       TEXT    DEFAULT '',
    modified_at      TEXT    DEFAULT ''
);

-- FTS5 index for package search
-- Content table mirrors `packages` for efficient updates
CREATE VIRTUAL TABLE IF NOT EXISTS packages_fts USING fts5(
    title,
    sub_title,
    short_description,
    description,
    category,
    types,
    destinations,
    content='packages',
    content_rowid='package_id',
    tokenize='porter ascii'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS packages_ai AFTER INSERT ON packages BEGIN
    INSERT INTO packages_fts(rowid, title, sub_title, short_description,
        description, category, types, destinations)
    VALUES (new.package_id, new.title, new.sub_title, new.short_description,
        new.description, new.category, new.types, new.destinations);
END;

CREATE TRIGGER IF NOT EXISTS packages_ad AFTER DELETE ON packages BEGIN
    INSERT INTO packages_fts(packages_fts, rowid, title, sub_title,
        short_description, description, category, types, destinations)
    VALUES ('delete', old.package_id, old.title, old.sub_title,
        old.short_description, old.description, old.category, old.types,
        old.destinations);
END;

CREATE TRIGGER IF NOT EXISTS packages_au AFTER UPDATE ON packages BEGIN
    INSERT INTO packages_fts(packages_fts, rowid, title, sub_title,
        short_description, description, category, types, destinations)
    VALUES ('delete', old.package_id, old.title, old.sub_title,
        old.short_description, old.description, old.category, old.types,
        old.destinations);
    INSERT INTO packages_fts(rowid, title, sub_title, short_description,
        description, category, types, destinations)
    VALUES (new.package_id, new.title, new.sub_title, new.short_description,
        new.description, new.category, new.types, new.destinations);
END;


-- ---------------------------------------------------------------------------
-- Hotels
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hotels (
    hotel_id         TEXT    PRIMARY KEY,
    name             TEXT    NOT NULL,
    city             TEXT    DEFAULT '',
    address          TEXT    DEFAULT '',
    region           TEXT    DEFAULT '',
    rating           TEXT    DEFAULT '',
    short_description TEXT   DEFAULT '',
    description      TEXT    DEFAULT '',
    facilities       TEXT    DEFAULT '',   -- pipe-separated list
    permalink        TEXT    DEFAULT '',
    status           INTEGER DEFAULT 1,
    created_at       TEXT    DEFAULT ''
);

CREATE VIRTUAL TABLE IF NOT EXISTS hotels_fts USING fts5(
    name,
    city,
    region,
    short_description,
    description,
    facilities,
    rating,
    content='hotels',
    content_rowid='rowid',
    tokenize='porter ascii'
);

CREATE TRIGGER IF NOT EXISTS hotels_ai AFTER INSERT ON hotels BEGIN
    INSERT INTO hotels_fts(rowid, name, city, region, short_description,
        description, facilities, rating)
    VALUES (new.rowid, new.name, new.city, new.region, new.short_description,
        new.description, new.facilities, new.rating);
END;

CREATE TRIGGER IF NOT EXISTS hotels_ad AFTER DELETE ON hotels BEGIN
    INSERT INTO hotels_fts(hotels_fts, rowid, name, city, region,
        short_description, description, facilities, rating)
    VALUES ('delete', old.rowid, old.name, old.city, old.region,
        old.short_description, old.description, old.facilities, old.rating);
END;

CREATE TRIGGER IF NOT EXISTS hotels_au AFTER UPDATE ON hotels BEGIN
    INSERT INTO hotels_fts(hotels_fts, rowid, name, city, region,
        short_description, description, facilities, rating)
    VALUES ('delete', old.rowid, old.name, old.city, old.region,
        old.short_description, old.description, old.facilities, old.rating);
    INSERT INTO hotels_fts(rowid, name, city, region, short_description,
        description, facilities, rating)
    VALUES (new.rowid, new.name, new.city, new.region, new.short_description,
        new.description, new.facilities, new.rating);
END;


-- ---------------------------------------------------------------------------
-- Itineraries
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS itineraries (
    itinerary_id     TEXT    PRIMARY KEY,
    package_hash_id  TEXT    NOT NULL,
    package_title    TEXT    DEFAULT '',
    day              INTEGER DEFAULT 0,
    title            TEXT    DEFAULT '',
    details          TEXT    DEFAULT '',
    created_at       TEXT    DEFAULT '',
    FOREIGN KEY (package_hash_id) REFERENCES packages(hash_id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_itineraries_package
    ON itineraries(package_hash_id);

CREATE VIRTUAL TABLE IF NOT EXISTS itineraries_fts USING fts5(
    package_title,
    title,
    details,
    content='itineraries',
    content_rowid='rowid',
    tokenize='porter ascii'
);

CREATE TRIGGER IF NOT EXISTS itineraries_ai AFTER INSERT ON itineraries BEGIN
    INSERT INTO itineraries_fts(rowid, package_title, title, details)
    VALUES (new.rowid, new.package_title, new.title, new.details);
END;

CREATE TRIGGER IF NOT EXISTS itineraries_ad AFTER DELETE ON itineraries BEGIN
    INSERT INTO itineraries_fts(itineraries_fts, rowid, package_title, title, details)
    VALUES ('delete', old.rowid, old.package_title, old.title, old.details);
END;

CREATE TRIGGER IF NOT EXISTS itineraries_au AFTER UPDATE ON itineraries BEGIN
    INSERT INTO itineraries_fts(itineraries_fts, rowid, package_title, title, details)
    VALUES ('delete', old.rowid, old.package_title, old.title, old.details);
    INSERT INTO itineraries_fts(rowid, package_title, title, details)
    VALUES (new.rowid, new.package_title, new.title, new.details);
END;


-- ---------------------------------------------------------------------------
-- Visa
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS visa (
    visa_id          TEXT    PRIMARY KEY,
    country          TEXT    NOT NULL UNIQUE,
    requirements     TEXT    DEFAULT '',
    status           INTEGER DEFAULT 1,
    created_at       TEXT    DEFAULT ''
);

CREATE VIRTUAL TABLE IF NOT EXISTS visa_fts USING fts5(
    country,
    requirements,
    content='visa',
    content_rowid='rowid',
    tokenize='porter ascii'
);

CREATE TRIGGER IF NOT EXISTS visa_ai AFTER INSERT ON visa BEGIN
    INSERT INTO visa_fts(rowid, country, requirements)
    VALUES (new.rowid, new.country, new.requirements);
END;

CREATE TRIGGER IF NOT EXISTS visa_ad AFTER DELETE ON visa BEGIN
    INSERT INTO visa_fts(visa_fts, rowid, country, requirements)
    VALUES ('delete', old.rowid, old.country, old.requirements);
END;

CREATE TRIGGER IF NOT EXISTS visa_au AFTER UPDATE ON visa BEGIN
    INSERT INTO visa_fts(visa_fts, rowid, country, requirements)
    VALUES ('delete', old.rowid, old.country, old.requirements);
    INSERT INTO visa_fts(rowid, country, requirements)
    VALUES (new.rowid, new.country, new.requirements);
END;


-- ---------------------------------------------------------------------------
-- Package-Hotel linking table (many-to-many)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS package_hotel_items (
    package_hash_id  TEXT NOT NULL,
    hotel_id         TEXT NOT NULL,
    sort_order       INTEGER DEFAULT 0,
    PRIMARY KEY (package_hash_id, hotel_id),
    FOREIGN KEY (package_hash_id) REFERENCES packages(hash_id) ON DELETE CASCADE,
    FOREIGN KEY (hotel_id)        REFERENCES hotels(hotel_id)  ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_phi_package
    ON package_hotel_items(package_hash_id);

CREATE INDEX IF NOT EXISTS idx_phi_hotel
    ON package_hotel_items(hotel_id);
