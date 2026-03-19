"""Re-collect reviews only: top 100 (filter=all) + recent up to 1000 (filter=recent)."""
import sys, os, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "steam-crawler", "src"))

from dotenv import load_dotenv
load_dotenv()

from steam_crawler.db.schema import init_db
from steam_crawler.api.steam_reviews import SteamReviewsClient
from steam_crawler.api.resilience import FailureTracker
from steam_crawler.db.repository import insert_reviews_batch
from steam_crawler.models.review import Review

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "steam.db")
TARGET_REVIEWS = 1000

conn = init_db(DB_PATH)
conn.row_factory = __import__("sqlite3").Row
tracker = FailureTracker()

games = conn.execute("SELECT appid, name FROM games ORDER BY positive DESC").fetchall()
print(f"=== {len(games)} games ===\n")

# ── Step 3a: Top reviews (filter=all, max 100) ──────────────────────
print("--- Step 3a: Top reviews (filter=all, max 100 per game) ---")
rev = SteamReviewsClient()
for g in games:
    appid, name = g["appid"], g["name"]
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
        else:
            print(f"  {name}: no reviews")
    except Exception as e:
        tracker.log_failure(conn=conn, session_id=0, api_name="steam_reviews",
                          appid=appid, step="step3a", error_message=str(e))
        print(f"  ERROR {name}: {e}")
rev.close()

# ── Step 3b: Recent reviews (filter=recent, up to 1000) ─────────────
print(f"\n--- Step 3b: Recent reviews (filter=recent, target={TARGET_REVIEWS}) ---")

games_need = []
for g in games:
    cnt = conn.execute("SELECT COUNT(*) FROM reviews WHERE appid=?", (g["appid"],)).fetchone()[0]
    if cnt < TARGET_REVIEWS:
        games_need.append((g["appid"], g["name"], cnt))

print(f"  {len(games_need)} games need more reviews\n")

rev = SteamReviewsClient()
for appid, name, _ in games_need:
    db_count = conn.execute("SELECT COUNT(*) FROM reviews WHERE appid=?", (appid,)).fetchone()[0]
    if db_count >= TARGET_REVIEWS:
        continue

    print(f"  [{appid}] {name}: have {db_count}...", end="", flush=True)
    cursor_val = "*"
    pages = 0
    try:
        while True:
            reviews, cursor_val, has_more = rev.fetch_reviews_page(appid, cursor=cursor_val)
            if not reviews:
                break
            insert_reviews_batch(conn, reviews, version=0)
            pages += 1
            db_count = conn.execute("SELECT COUNT(*) FROM reviews WHERE appid=?", (appid,)).fetchone()[0]
            if db_count >= TARGET_REVIEWS or not has_more or not cursor_val:
                break
        print(f" -> {pages} pages, total: {db_count}")
    except Exception as e:
        tracker.log_failure(conn=conn, session_id=0, api_name="steam_reviews",
                          appid=appid, step="step3b", error_message=str(e))
        print(f" ERROR: {e}")
rev.close()

# ── Summary ──────────────────────────────────────────────────────────
print("\n=== SUMMARY ===")
total_reviews = 0
under = 0
for g in games:
    cnt = conn.execute("SELECT COUNT(*) FROM reviews WHERE appid=?", (g["appid"],)).fetchone()[0]
    total_reviews += cnt
    if cnt < TARGET_REVIEWS:
        under += 1
        avail = conn.execute("SELECT COALESCE(steam_positive,0)+COALESCE(steam_negative,0) FROM games WHERE appid=?",
                            (g["appid"],)).fetchone()[0]
        if avail < TARGET_REVIEWS:
            print(f"  {g['name']}: {cnt} (max available: {avail})")
        else:
            print(f"  {g['name']}: {cnt}/{TARGET_REVIEWS}")

print(f"\nTotal reviews: {total_reviews:,}")
print(f"At target: {len(games)-under}/{len(games)} | Under: {under}")
conn.close()
print("Done!")
