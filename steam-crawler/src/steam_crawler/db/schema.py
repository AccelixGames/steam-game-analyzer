"""SQLite schema initialization for steam-crawler."""

import sqlite3
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS games (
    appid          INTEGER PRIMARY KEY,
    name           TEXT NOT NULL,
    positive       INTEGER,
    negative       INTEGER,
    owners         TEXT,
    price          INTEGER,
    avg_playtime   INTEGER,
    score_rank     TEXT,
    steam_positive INTEGER,
    steam_negative INTEGER,
    review_score   TEXT,
    short_description_en TEXT,
    short_description_ko TEXT,
    header_image   TEXT,
    source_tag     TEXT,
    first_seen_ver INTEGER,
    updated_at     TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reviews (
    recommendation_id TEXT PRIMARY KEY,
    appid            INTEGER REFERENCES games(appid),
    language         TEXT,
    review_text      TEXT,
    voted_up         BOOLEAN,
    playtime_forever INTEGER,
    playtime_at_review INTEGER,
    early_access     BOOLEAN,
    steam_purchase   BOOLEAN,
    received_for_free BOOLEAN,
    dev_response     TEXT,
    timestamp_created INTEGER,
    votes_up         INTEGER,
    votes_funny      INTEGER,
    weighted_vote_score REAL,
    comment_count    INTEGER,
    author_steamid   TEXT,
    author_num_reviews INTEGER,
    author_playtime_forever INTEGER,
    collected_ver    INTEGER,
    collected_at     TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_reviews_appid ON reviews(appid);
CREATE INDEX IF NOT EXISTS idx_reviews_language ON reviews(language);
CREATE INDEX IF NOT EXISTS idx_reviews_voted_up ON reviews(voted_up);

CREATE TABLE IF NOT EXISTS data_versions (
    version       INTEGER PRIMARY KEY AUTOINCREMENT,
    query_type    TEXT NOT NULL,
    query_value   TEXT,
    status        TEXT NOT NULL,
    games_total   INTEGER,
    reviews_total INTEGER,
    config        TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    note          TEXT
);

CREATE TABLE IF NOT EXISTS changelog (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    version       INTEGER REFERENCES data_versions(version),
    change_type   TEXT NOT NULL,
    appid         INTEGER,
    field_name    TEXT,
    old_value     TEXT,
    new_value     TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_changelog_version ON changelog(version);
CREATE INDEX IF NOT EXISTS idx_changelog_appid ON changelog(appid);

CREATE TABLE IF NOT EXISTS rate_limit_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    api_name        TEXT NOT NULL,
    session_id      INTEGER REFERENCES data_versions(version),
    requests_made   INTEGER,
    errors_429      INTEGER DEFAULT 0,
    errors_5xx      INTEGER DEFAULT 0,
    avg_response_ms REAL,
    optimal_delay_ms REAL,
    recorded_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS failure_logs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      INTEGER REFERENCES data_versions(version),
    api_name        TEXT NOT NULL,
    appid           INTEGER,
    step            TEXT,
    failure_type    TEXT NOT NULL,
    http_status     INTEGER,
    error_message   TEXT,
    request_url     TEXT,
    response_body   TEXT,
    retry_count     INTEGER DEFAULT 0,
    resolved        BOOLEAN DEFAULT 0,
    resolution      TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_failure_logs_type ON failure_logs(failure_type);
CREATE INDEX IF NOT EXISTS idx_failure_logs_session ON failure_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_failure_logs_unresolved ON failure_logs(resolved) WHERE resolved = 0;

CREATE TABLE IF NOT EXISTS tag_catalog (
    tag_name       TEXT PRIMARY KEY,
    total_games    INTEGER,
    fetched_at     TIMESTAMP
);

CREATE TABLE IF NOT EXISTS game_tags (
    appid          INTEGER REFERENCES games(appid),
    tag_name       TEXT REFERENCES tag_catalog(tag_name),
    vote_count     INTEGER NOT NULL,
    PRIMARY KEY (appid, tag_name)
);

CREATE INDEX IF NOT EXISTS idx_game_tags_tag ON game_tags(tag_name);

CREATE TABLE IF NOT EXISTS genre_catalog (
    genre_name     TEXT PRIMARY KEY,
    total_games    INTEGER,
    fetched_at     TIMESTAMP
);

CREATE TABLE IF NOT EXISTS game_genres (
    appid          INTEGER REFERENCES games(appid),
    genre_name     TEXT REFERENCES genre_catalog(genre_name),
    PRIMARY KEY (appid, genre_name)
);

CREATE INDEX IF NOT EXISTS idx_game_genres_genre ON game_genres(genre_name);

CREATE TABLE IF NOT EXISTS game_media (
    appid          INTEGER REFERENCES games(appid),
    media_type     TEXT NOT NULL,
    media_id       INTEGER NOT NULL,
    name           TEXT,
    url_thumbnail  TEXT,
    url_full       TEXT,
    PRIMARY KEY (appid, media_type, media_id)
);

CREATE INDEX IF NOT EXISTS idx_game_media_appid ON game_media(appid);

CREATE TABLE IF NOT EXISTS game_collection_status (
    appid           INTEGER,
    version         INTEGER REFERENCES data_versions(version),
    steamspy_done   BOOLEAN DEFAULT 0,
    summary_done    BOOLEAN DEFAULT 0,
    reviews_done    BOOLEAN DEFAULT 0,
    last_cursor     TEXT,
    reviews_collected INTEGER DEFAULT 0,
    reviews_total     INTEGER,
    languages_done  TEXT,
    review_types_done TEXT,
    updated_at      TIMESTAMP,
    PRIMARY KEY (appid, version)
);
"""


def init_db(db_path: str) -> sqlite3.Connection:
    """Initialize the database with schema. Returns connection."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA_SQL)
    return conn
