"""SQLite schema initialization for steam-crawler."""

import sqlite3
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS games (
    appid          INTEGER PRIMARY KEY,
    name           TEXT NOT NULL,
    name_ko        TEXT,
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
    detailed_description_en TEXT,
    detailed_description_ko TEXT,
    header_image   TEXT,
    igdb_id          INTEGER,
    igdb_summary     TEXT,
    igdb_storyline   TEXT,
    igdb_rating      REAL,
    rawg_id          INTEGER,
    rawg_description TEXT,
    rawg_rating      REAL,
    metacritic_score INTEGER,
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

CREATE TABLE IF NOT EXISTS theme_catalog (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS game_themes (
    appid    INTEGER NOT NULL,
    theme_id INTEGER NOT NULL,
    source   TEXT NOT NULL DEFAULT 'igdb',
    PRIMARY KEY (appid, theme_id),
    FOREIGN KEY (appid) REFERENCES games(appid),
    FOREIGN KEY (theme_id) REFERENCES theme_catalog(id)
);

CREATE INDEX IF NOT EXISTS idx_game_themes_theme ON game_themes(theme_id);

CREATE TABLE IF NOT EXISTS keyword_catalog (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS game_keywords (
    appid      INTEGER NOT NULL,
    keyword_id INTEGER NOT NULL,
    source     TEXT NOT NULL DEFAULT 'igdb',
    PRIMARY KEY (appid, keyword_id),
    FOREIGN KEY (appid) REFERENCES games(appid),
    FOREIGN KEY (keyword_id) REFERENCES keyword_catalog(id)
);

CREATE INDEX IF NOT EXISTS idx_game_keywords_keyword ON game_keywords(keyword_id);

CREATE INDEX IF NOT EXISTS idx_games_igdb_id ON games(igdb_id);
CREATE INDEX IF NOT EXISTS idx_games_rawg_id ON games(rawg_id);

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

CREATE TABLE IF NOT EXISTS crawl_locks (
    appid       INTEGER PRIMARY KEY,
    locked_at   TIMESTAMP NOT NULL,
    expires_at  TIMESTAMP NOT NULL,
    owner       TEXT
);

CREATE TABLE IF NOT EXISTS external_reviews (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    appid         INTEGER REFERENCES games(appid),
    source        TEXT NOT NULL,
    source_id     TEXT,
    title         TEXT,
    score         REAL,
    author        TEXT,
    outlet        TEXT,
    url           TEXT,
    snippet       TEXT,
    view_count    INTEGER,
    like_ratio    REAL,
    published_at  TIMESTAMP,
    fetched_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(appid, source, source_id)
);

CREATE INDEX IF NOT EXISTS idx_ext_reviews_appid ON external_reviews(appid);
CREATE INDEX IF NOT EXISTS idx_ext_reviews_source ON external_reviews(source);

CREATE TABLE IF NOT EXISTS game_wikidata_claims (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    appid       INTEGER NOT NULL REFERENCES games(appid),
    claim_type  TEXT NOT NULL,
    name        TEXT NOT NULL,
    wikidata_id TEXT,
    property_id TEXT,
    extra       TEXT,
    fetched_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(appid, claim_type, wikidata_id)
);

CREATE INDEX IF NOT EXISTS idx_wdc_appid ON game_wikidata_claims(appid);
CREATE INDEX IF NOT EXISTS idx_wdc_type ON game_wikidata_claims(claim_type);
CREATE INDEX IF NOT EXISTS idx_wdc_name ON game_wikidata_claims(name);
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
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns that may be missing in older databases."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(games)").fetchall()}
    migrations = [
        ("name_ko", "TEXT"),
        ("detailed_description_en", "TEXT"),
        ("detailed_description_ko", "TEXT"),
        # RAWG retention proxy
        ("rawg_ratings_count", "INTEGER"),
        ("rawg_added", "INTEGER"),
        ("rawg_status_yet", "INTEGER"),
        ("rawg_status_owned", "INTEGER"),
        ("rawg_status_beaten", "INTEGER"),
        ("rawg_status_toplay", "INTEGER"),
        ("rawg_status_dropped", "INTEGER"),
        ("rawg_status_playing", "INTEGER"),
        ("rawg_exceptional_pct", "REAL"),
        ("rawg_recommended_pct", "REAL"),
        ("rawg_meh_pct", "REAL"),
        ("rawg_skip_pct", "REAL"),
        # Twitch streaming
        ("twitch_game_id", "TEXT"),
        ("twitch_stream_count", "INTEGER"),
        ("twitch_viewer_count", "INTEGER"),
        ("twitch_top_language", "TEXT"),
        ("twitch_lang_distribution", "TEXT"),
        ("twitch_fetched_at", "TIMESTAMP"),
        # HowLongToBeat
        ("hltb_id", "INTEGER"),
        ("hltb_main_story", "REAL"),
        ("hltb_main_extra", "REAL"),
        ("hltb_completionist", "REAL"),
        # CheapShark
        ("cheapshark_deal_rating", "REAL"),
        ("cheapshark_lowest_price", "REAL"),
        ("cheapshark_lowest_price_date", "TEXT"),
        # OpenCritic
        ("opencritic_id", "INTEGER"),
        ("opencritic_score", "REAL"),
        ("opencritic_pct_recommend", "REAL"),
        ("opencritic_tier", "TEXT"),
        ("opencritic_review_count", "INTEGER"),
        # Wikidata
        ("wikidata_id", "TEXT"),
        ("wikidata_fetched_at", "TIMESTAMP"),
        # PCGamingWiki
        ("pcgw_engine", "TEXT"),
        ("pcgw_has_ultrawide", "INTEGER"),
        ("pcgw_has_hdr", "INTEGER"),
        ("pcgw_has_controller", "INTEGER"),
        ("pcgw_graphics_api", "TEXT"),
    ]
    for col, col_type in migrations:
        if col not in existing:
            conn.execute(f"ALTER TABLE games ADD COLUMN {col} {col_type}")
    conn.commit()
    # Indexes on migrated columns
    conn.execute("CREATE INDEX IF NOT EXISTS idx_games_opencritic_id ON games(opencritic_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_games_hltb_id ON games(hltb_id)")
    conn.commit()
