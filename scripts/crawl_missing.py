"""Crawl all games with missing data. Reviews up to 1000 by relevance (filter=all)."""
import sys, os, time, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "steam-crawler", "src"))

from dotenv import load_dotenv
load_dotenv()

from steam_crawler.db.schema import init_db
from steam_crawler.api.steam_store import SteamStoreClient
from steam_crawler.api.steam_reviews import SteamReviewsClient
from steam_crawler.api.steamspy import SteamSpyClient
from steam_crawler.api.igdb import IGDBClient
from steam_crawler.api.rawg import RAWGClient
from steam_crawler.api.resilience import FailureTracker
from steam_crawler.db.repository import (
    upsert_game_tags, upsert_game_genres,
    update_game_store_details, upsert_game_media,
    update_game_review_stats, insert_reviews_batch,
    update_game_igdb_details, upsert_game_themes, upsert_game_keywords,
    update_game_rawg_details,
)
from steam_crawler.pipeline.step1d_igdb import run_step1d
from steam_crawler.pipeline.step1e_rawg import run_step1e

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "steam.db")
TARGET_REVIEWS = 1000

conn = init_db(DB_PATH)
conn.row_factory = __import__("sqlite3").Row
tracker = FailureTracker()

# ── Identify games needing work ──────────────────────────────────────
games = conn.execute("SELECT appid, name FROM games ORDER BY positive DESC").fetchall()
print(f"\n=== Total games: {len(games)} ===\n")

# ── Step 1b: Tags/Genres (for games missing them) ───────────────────
games_no_tags = [g for g in games if conn.execute(
    "SELECT COUNT(*) FROM game_tags WHERE appid=?", (g["appid"],)).fetchone()[0] == 0]

if games_no_tags:
    print(f"\n--- Step 1b: Fetching tags for {len(games_no_tags)} games ---")
    spy = SteamSpyClient()
    for g in games_no_tags:
        try:
            details = spy.fetch_app_details(g["appid"])
            if details.tags:
                upsert_game_tags(conn, g["appid"], details.tags)
            if details.genres:
                upsert_game_genres(conn, g["appid"], details.genres)
            print(f"  Tags: {g['name']} - {len(details.tags or {})} tags")
        except Exception as e:
            print(f"  ERROR tags {g['name']}: {e}")
    spy.close()

# ── Step 1c: Store details (for games missing them) ─────────────────
games_no_store = [g for g in games if conn.execute(
    "SELECT short_description_en FROM games WHERE appid=?", (g["appid"],)
).fetchone()[0] is None and conn.execute(
    "SELECT short_description_ko FROM games WHERE appid=?", (g["appid"],)
).fetchone()[0] is None]

if games_no_store:
    print(f"\n--- Step 1c: Fetching store details for {len(games_no_store)} games ---")
    store = SteamStoreClient()
    for g in games_no_store:
        try:
            details = store.fetch_app_details(g["appid"])
            if details:
                update_game_store_details(
                    conn, appid=g["appid"],
                    short_description_en=details.short_description_en,
                    short_description_ko=details.short_description_ko,
                    detailed_description_en=details.detailed_description_en,
                    detailed_description_ko=details.detailed_description_ko,
                    header_image=details.header_image,
                )
                for media in details.media:
                    upsert_game_media(
                        conn, appid=g["appid"],
                        media_type=media.media_type, media_id=media.media_id,
                        name=media.name, url_thumbnail=media.url_thumbnail,
                        url_full=media.url_full,
                    )
                print(f"  Store: {g['name']} - {len(details.media)} media items")
            else:
                print(f"  Store: {g['name']} - no data returned")
        except Exception as e:
            tracker.log_failure(conn=conn, session_id=0, api_name="steam_store",
                              appid=g["appid"], step="step1c", error_message=str(e))
            print(f"  ERROR store {g['name']}: {e}")
    store.close()

# ── Step 1d: IGDB ────────────────────────────────────────────────────
igdb_cid = os.getenv("TWITCH_CLIENT_ID")
igdb_sec = os.getenv("TWITCH_CLIENT_SECRET")
if igdb_cid and igdb_sec:
    print("\n--- Step 1d: IGDB enrichment ---")
    run_step1d(conn, version=0, client_id=igdb_cid, client_secret=igdb_sec,
               failure_tracker=tracker)
else:
    print("\n--- Step 1d: SKIPPED (no TWITCH credentials) ---")

# ── Step 1e: RAWG ────────────────────────────────────────────────────
rawg_key = os.getenv("RAWG_API_KEY")
if rawg_key:
    print("\n--- Step 1e: RAWG enrichment ---")
    run_step1e(conn, version=0, api_key=rawg_key, failure_tracker=tracker)
else:
    print("\n--- Step 1e: SKIPPED (no RAWG_API_KEY) ---")

# ── Step 2: Review summaries (for games missing them) ────────────────
games_no_stats = [g for g in games if conn.execute(
    "SELECT steam_positive FROM games WHERE appid=?", (g["appid"],)
).fetchone()[0] is None]

if games_no_stats:
    print(f"\n--- Step 2: Fetching review stats for {len(games_no_stats)} games ---")
    rev = SteamReviewsClient()
    for g in games_no_stats:
        try:
            summary = rev.fetch_summary(g["appid"])
            update_game_review_stats(
                conn, appid=g["appid"],
                steam_positive=summary.total_positive,
                steam_negative=summary.total_negative,
                review_score=summary.review_score_desc,
            )
            print(f"  Stats: {g['name']} - +{summary.total_positive}/-{summary.total_negative}")
        except Exception as e:
            tracker.log_failure(conn=conn, session_id=0, api_name="steam_reviews_summary",
                              appid=g["appid"], step="step2", error_message=str(e))
            print(f"  ERROR stats {g['name']}: {e}")
    rev.close()

# ── Step 3a: Top reviews (filter=all, max 100) ──────────────────────
print(f"\n--- Step 3a: Collecting top reviews (filter=all, max 100) ---")
from steam_crawler.models.review import Review

rev = SteamReviewsClient()
for g in games:
    appid = g["appid"]
    name = g["name"]
    try:
        cursor_val = "*"
        batch = []
        while len(batch) < 100:
            response = rev._client.get(
                f"https://store.steampowered.com/appreviews/{appid}",
                params={"json": "1", "cursor": cursor_val, "filter": "all",
                        "purchase_type": "all", "num_per_page": "80",
                        "language": "all", "review_type": "all"},
            )
            response.raise_for_status()
            data = response.json()
            reviews_data = data.get("reviews", [])
            if not reviews_data:
                break
            batch.extend(Review.from_steam_api(r, appid=appid) for r in reviews_data)
            next_cursor = data.get("cursor", "")
            if not next_cursor or next_cursor == cursor_val:
                break
            cursor_val = next_cursor
        if batch:
            inserted = insert_reviews_batch(conn, batch[:100], version=0)
            print(f"  {name}: {inserted} top reviews")
    except Exception as e:
        tracker.log_failure(conn=conn, session_id=0, api_name="steam_reviews",
                          appid=appid, step="step3a", error_message=str(e))
        print(f"  ERROR {name}: {e}")
rev.close()

# ── Step 3b: Recent reviews (filter=recent, up to 1000) ─────────────
print(f"\n--- Step 3b: Collecting recent reviews (filter=recent, target={TARGET_REVIEWS}) ---")

games_need_reviews = []
for g in games:
    cnt = conn.execute("SELECT COUNT(*) FROM reviews WHERE appid=?", (g["appid"],)).fetchone()[0]
    if cnt < TARGET_REVIEWS:
        games_need_reviews.append((g, cnt))

print(f"  {len(games_need_reviews)} games need more reviews\n")

rev = SteamReviewsClient()
for g, current_count in games_need_reviews:
    appid = g["appid"]
    name = g["name"]

    # Check actual DB count each iteration (not stale)
    db_count = conn.execute("SELECT COUNT(*) FROM reviews WHERE appid=?", (appid,)).fetchone()[0]
    if db_count >= TARGET_REVIEWS:
        continue

    print(f"  [{appid}] {name}: have {db_count}, target {TARGET_REVIEWS}...")

    cursor_val = "*"
    pages = 0
    try:
        while True:
            reviews, cursor_val, has_more = rev.fetch_reviews_page(appid, cursor=cursor_val)
            if not reviews:
                break
            inserted = insert_reviews_batch(conn, reviews, version=0)
            pages += 1

            # Re-check actual DB count after each batch
            db_count = conn.execute("SELECT COUNT(*) FROM reviews WHERE appid=?", (appid,)).fetchone()[0]
            if db_count >= TARGET_REVIEWS:
                break
            if not has_more or not cursor_val:
                break

        print(f"    -> {pages} pages, total now: {db_count}")

    except Exception as e:
        tracker.log_failure(conn=conn, session_id=0, api_name="steam_reviews",
                          appid=appid, step="step3b", error_message=str(e))
        print(f"    ERROR: {e}")

rev.close()

# ── Summary ──────────────────────────────────────────────────────────
print("\n=== DONE ===")
for g in games:
    cnt = conn.execute("SELECT COUNT(*) FROM reviews WHERE appid=?", (g["appid"],)).fetchone()[0]
    tags = conn.execute("SELECT COUNT(*) FROM game_tags WHERE appid=?", (g["appid"],)).fetchone()[0]
    media = conn.execute("SELECT COUNT(*) FROM game_media WHERE appid=?", (g["appid"],)).fetchone()[0]
    row = conn.execute("SELECT igdb_summary, rawg_description, short_description_en FROM games WHERE appid=?",
                       (g["appid"],)).fetchone()
    status = "OK" if (cnt >= TARGET_REVIEWS and tags > 0 and row[0] and row[1] and row[2]) else "PARTIAL"
    if cnt < TARGET_REVIEWS or tags == 0:
        print(f"  [{g['appid']}] {g['name']}: reviews={cnt} tags={tags} media={media} [{status}]")

conn.close()
print("\nAll done!")
