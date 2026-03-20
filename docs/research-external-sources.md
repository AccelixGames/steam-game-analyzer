# External Sources Research: Game Evaluations, Design Analysis & Reviews

> Research date: 2026-03-19
> Purpose: Identify APIs and data sources to enrich Steam game database with external perspectives

---

## Priority Matrix (Implementation Recommendation)

| Priority | Source | Effort | Value | Auth |
|----------|--------|--------|-------|------|
| **P0** | OpenCritic API | Low | High | RapidAPI key |
| **P0** | HowLongToBeat | Low | High | None (scraping) |
| **P0** | ProtonDB | Low | Medium | None |
| **P1** | YouTube Data API v3 | Medium | High | Google API key |
| **P1** | PCGamingWiki | Medium | High | None |
| **P1** | IsThereAnyDeal | Low | Medium | API key |
| **P1** | CheapShark | Low | Medium | None |
| **P1** | SteamSpy | Low | Medium | None |
| **P2** | Reddit (PRAW) | Medium | Medium | OAuth2 |
| **P2** | GiantBomb | Low | Medium | API key |
| **P2** | Metacritic (scraping) | High | High | None (scraping, fragile) |
| **P3** | Gaming RSS Feeds | Low | Low | None |
| **P3** | Korean Sources | High | Low | None (scraping) |

---

## 1. Metacritic

### Status: No Official API -- Scraping Only

| Field | Detail |
|-------|--------|
| URL | `https://www.metacritic.com/game/{slug}` |
| Auth | None (web scraping) |
| Rate Limits | Custom -- add 2s+ delay between requests |
| Format | HTML scraping (BeautifulSoup) |
| Legal | ToS prohibits scraping; use with caution |

### Data Available
- Metascore (critic aggregate, 0-100)
- User score (0-10)
- Critic review count
- User review count
- Individual critic scores + excerpts + publication name
- Platform-specific scores

### Python Libraries
- **pycritic** (`pip install pycritic`) -- BeautifulSoup-based scraper, fragile
- **Apify Metacritic Scraper** -- cloud-based, JSON output, but only Metascores (no user scores from search)
- **RapidAPI MetacriticAPI** -- third-party wrapper, paid tiers

### Anti-Bot Measures (2025-2026)
- Cloudflare protection detected
- Requires TLS fingerprint impersonation (`curl_cffi`) or browser automation (Playwright)
- Proxy rotation recommended for production
- Headers must mimic real browser

### Practical Assessment
**NOT RECOMMENDED as primary source.** Fragile scraping, legal risk, anti-bot measures. Use RAWG's `metacritic` field instead (already integrated in step1e) for the numeric score. Only pursue if individual critic review excerpts are needed.

---

## 2. OpenCritic API

### Status: Official API via RapidAPI -- RECOMMENDED

| Field | Detail |
|-------|--------|
| URL | `https://opencritic-api.p.rapidapi.com/` |
| Docs | https://app.swaggerhub.com/apis-docs/OpenCritic/OpenCritic-API/0.1 |
| Auth | RapidAPI key (`X-RapidAPI-Key` header) |
| Rate Limits | Free tier: ~25 requests/day; Basic: higher |
| Format | JSON |
| Legal | Official API with ToS: https://c.opencritic.com/OpenCriticAPIAgreement.pdf |

### Key Endpoints
```
GET /game/search?criteria={name}        -- Search games
GET /game/{id}                          -- Game details (topCriticScore, percentRecommended, tier)
GET /game/{id}/reviews                  -- Individual critic reviews
GET /game/{id}/reviews?sort=score       -- Sorted reviews
```

### Data Available
- **topCriticScore** (0-100, similar to Metacritic)
- **percentRecommended** (% of critics recommending)
- **tier** ("Mighty", "Strong", "Fair", "Weak")
- **numReviews** (total critic review count)
- **numTopCriticReviews**
- Individual review: score, snippet, outlet name, author, URL, date
- Platform information

### Python Integration
```python
import httpx

headers = {
    "X-RapidAPI-Key": "YOUR_KEY",
    "X-RapidAPI-Host": "opencritic-api.p.rapidapi.com",
}
# Search
r = httpx.get("https://opencritic-api.p.rapidapi.com/game/search",
              params={"criteria": "Hades"}, headers=headers)
# Game details
r = httpx.get(f"https://opencritic-api.p.rapidapi.com/game/{game_id}",
              headers=headers)
```

### Practical Assessment
**HIGH PRIORITY.** Clean JSON API, official, provides critic aggregate scores AND individual review data. Free tier is limited (25/day) but sufficient for batch enrichment of newly crawled games. Pairs well with our RAWG metacritic_score for cross-validation.

---

## 3. IGDB (Already Integrated -- Additional Data)

### Current Integration
We already have step1d_igdb fetching: `igdb_id`, `igdb_url`, themes, keywords, game modes, player perspectives.

### Additional Endpoints Worth Adding

| Endpoint | Data | Value |
|----------|------|-------|
| `/games` fields: `aggregated_rating`, `aggregated_rating_count` | Critic score aggregate from IGDB | Cross-reference with OpenCritic |
| `/games` fields: `rating`, `rating_count` | IGDB user rating | Additional user sentiment |
| `/games` fields: `hypes` | Pre-release hype count | Marketing analysis |
| `/games` fields: `follows` | IGDB followers | Community interest proxy |
| `/age_ratings` | Age rating (ESRB, PEGI) | Content classification |
| `/websites` | Official links (Steam, GOG, etc.) | Cross-platform presence |

### Rate Limits (Current)
- 4 requests/second (already handled by our AdaptiveRateLimiter)
- Free for non-commercial use via Twitch Developer

### Recommendation
Extend existing step1d to fetch `aggregated_rating`, `rating`, `hypes`, `follows` with minimal effort.

---

## 4. YouTube Data API v3

### Status: Official Google API -- RECOMMENDED for P1

| Field | Detail |
|-------|--------|
| URL | `https://www.googleapis.com/youtube/v3/` |
| Docs | https://developers.google.com/youtube/v3/docs |
| Auth | Google API key (free) |
| Rate Limits | 10,000 units/day (free); search = 100 units, video details = 1 unit |
| Format | JSON |
| Legal | Google ToS; no scraping needed |

### Key Endpoints
```
GET /search?q={game_name}+review&type=video&videoCategoryId=20
    -- Search game review videos (100 units)
GET /videos?id={id}&part=snippet,statistics,contentDetails
    -- Video details: views, likes, duration (1 unit)
GET /channels?id={id}&part=statistics
    -- Channel subscriber count (1 unit)
```

### Data Available Per Video
- **title, description, publishedAt** (snippet)
- **viewCount, likeCount, commentCount** (statistics)
- **duration** (contentDetails)
- **channelTitle, channelId** (to identify reviewer)
- **thumbnails** (various sizes)

### Notable Channels to Track
| Channel | Focus | Subscribers |
|---------|-------|-------------|
| SkillUp | In-depth reviews | ~2M |
| ACG | Buy/Wait/Rent/Never | ~1.5M |
| Gameranx (Before You Buy) | Purchase advice | ~9M |
| Angry Joe Show | Entertainment reviews | ~4M |
| Worth A Buy | PC-focused | ~700K |
| Digital Foundry | Technical analysis | ~2M |

### Quota Budget (10,000 units/day)
- 100 searches/day = 100 games
- Each search + 5 video details = 105 units/game
- Realistic: ~90 games/day with full metadata

### Python Libraries
- **google-api-python-client** (`pip install google-api-python-client`)
- **youtube-data-api** (`pip install youtube-data-api`) -- simpler wrapper

### Python Integration
```python
from googleapiclient.discovery import build

youtube = build("youtube", "v3", developerKey="YOUR_KEY")

# Search for game reviews
request = youtube.search().list(
    q=f"{game_name} review",
    type="video",
    part="snippet",
    maxResults=5,
    videoCategoryId="20",  # Gaming category
    order="relevance",
)
response = request.execute()

# Get video statistics
video_ids = [item["id"]["videoId"] for item in response["items"]]
stats = youtube.videos().list(
    id=",".join(video_ids),
    part="statistics,contentDetails"
).execute()
```

### Practical Assessment
**HIGH VALUE.** YouTube reviews represent the most influential game evaluation channel. View counts + like ratios provide sentiment signal. Can identify which games have strong "watchability" (complementing Twitch data). Quota is generous for daily batch enrichment.

---

## 5. Reddit API (PRAW)

### Status: Official API, Free for Non-Commercial Use

| Field | Detail |
|-------|--------|
| URL | `https://oauth.reddit.com/` |
| Docs | https://www.reddit.com/dev/api/ |
| Auth | OAuth2 (client_id + client_secret + user_agent) |
| Rate Limits | 60 requests/minute (authenticated) |
| Format | JSON |
| Legal | Free for non-commercial; Reddit ToS apply |

### Relevant Subreddits
| Subreddit | Members | Content |
|-----------|---------|---------|
| r/Games | 3.5M | Serious game discussion, reviews |
| r/pcgaming | 3.9M | PC-specific discussion |
| r/Steam | 1.5M | Steam platform discussion |
| r/truegaming | 1.3M | Deep analysis, design discussion |
| r/patientgamers | 900K | Retrospective reviews |
| r/gamedesign | 200K | Design analysis |

### Data Available
- Post title, body, score (upvotes), comment count
- Top comments with scores
- Flair tags (e.g., "Review", "Discussion")
- Search by game name within specific subreddits

### Python Library: PRAW
```python
import praw

reddit = praw.Reddit(
    client_id="YOUR_ID",
    client_secret="YOUR_SECRET",
    user_agent="steam-game-analyzer/1.0",
)

# Search for game discussion
for submission in reddit.subreddit("Games").search(
    f'"{game_name}"', sort="relevance", time_filter="year", limit=10
):
    print(submission.title, submission.score, submission.num_comments)
```

### Pushshift / Arctic Shift (Historical Data)
- **Pushshift** -- shut down by Reddit in 2024, but historical archives still available
- **Arctic Shift** (https://github.com/ArthurHeitmann/arctic_shift) -- academic project hosting Reddit data dumps via Academic Torrents
- Monthly archives in JSON format, downloadable for local analysis

### Practical Assessment
**MEDIUM PRIORITY.** Valuable for community sentiment beyond Steam reviews, but harder to structure. Best used for:
- Finding "controversial" games (high comment count, mixed votes)
- Identifying discussion themes not visible in Steam reviews
- Cross-referencing Steam sentiment with Reddit sentiment

---

## 6. HowLongToBeat

### Status: No Official API -- Python Wrappers Available

| Field | Detail |
|-------|--------|
| URL | `https://howlongtobeat.com/` |
| Auth | None |
| Rate Limits | Unofficial -- be respectful (1-2 req/s) |
| Format | JSON (via Python wrapper scraping) |
| Legal | No official API; scraping-based |

### Data Available
- **Main Story** completion time (hours)
- **Main + Extras** completion time
- **Completionist** completion time
- **Co-op / Multiplayer** times
- Game platforms, rating, description
- Number of submissions per category

### Python Libraries
- **howlongtobeatpy** (`pip install howlongtobeatpy`) -- most maintained, by ScrappyCocco
  - Auto-filters results by name similarity (>0.4)
  - Returns structured `HowLongToBeatEntry` objects

```python
from howlongtobeatpy import HowLongToBeat

results = await HowLongToBeat().async_search("Hades")
if results:
    best = max(results, key=lambda r: r.similarity)
    print(f"Main: {best.main_story}h")
    print(f"Main+Extra: {best.main_extra}h")
    print(f"Completionist: {best.completionist}h")
```

### Practical Assessment
**HIGH PRIORITY.** Game length is a critical design metric:
- Short main story + long completionist = content depth
- Ratio of main/completionist reveals "padding" vs "depth"
- Pairs well with Steam review analysis of "hours played" data
- Direct correlation with perceived "value for money"

---

## 7. PCGamingWiki

### Status: MediaWiki API -- Public, Free

| Field | Detail |
|-------|--------|
| URL | `https://www.pcgamingwiki.com/w/api.php` |
| Docs | https://www.pcgamingwiki.com/wiki/PCGamingWiki:API |
| Auth | None |
| Rate Limits | Standard MediaWiki limits (~200 req/min) |
| Format | JSON (via Cargo queries) |
| Legal | CC BY-NC-SA 3.0 license |

### Key API Calls

**Cargo Query (structured data):**
```
https://www.pcgamingwiki.com/w/api.php?action=cargoquery
  &tables=Infobox_game
  &fields=Steam_AppID,Developers,Publishers,Released,Reception
  &where=Steam_AppID="{appid}"
  &format=json
```

**Redirect by Steam AppID:**
```
https://www.pcgamingwiki.com/api/appid.php?appid={steam_appid}
```
Redirects to the game's wiki page.

### Data Available
- **Technical specs**: supported resolutions, frame rates, HDR, ultrawide
- **Input**: controller support quality, key rebinding
- **Audio**: surround sound, subtitles
- **Network**: multiplayer type, netcode details
- **Port quality indicators**: known issues, fixes
- **Save data locations**: paths for Steam Cloud saves
- **API used**: DirectX version, Vulkan support

### Python Integration
```python
import httpx

# Cargo query for technical data
r = httpx.get("https://www.pcgamingwiki.com/w/api.php", params={
    "action": "cargoquery",
    "tables": "Infobox_game",
    "fields": "Steam_AppID,Developers,Publishers,Engine",
    "where": f'Steam_AppID="{appid}"',
    "format": "json",
})
```

### Practical Assessment
**HIGH PRIORITY for technical analysis.** Unique data no other source provides:
- Port quality assessment (PC-specific)
- Engine information (Unity, Unreal, custom)
- Technical capabilities (ultrawide, HDR, controller)
- Complements our design analysis with "craft quality" dimension

---

## 8. ProtonDB

### Status: Unofficial Community API

| Field | Detail |
|-------|--------|
| URL | `https://www.protondb.com/api/v1/reports/summaries/{appid}.json` |
| Alt API | `https://protondb.max-p.me/` (community API by max-p) |
| Auth | None |
| Rate Limits | Unofficial -- be respectful |
| Format | JSON |
| Legal | Community data, no official ToS for API |

### Data Available
- **tier**: "platinum", "gold", "silver", "bronze", "borked"
- **total** reports count
- **trendingTier**: recent trend direction
- **bestReportedTier**: best achieved compatibility
- **confidence**: "good", "moderate", "low"
- Individual reports with hardware specs, game settings, notes

### Endpoints
```
# Summary (fast, lightweight)
GET https://www.protondb.com/api/v1/reports/summaries/{steam_appid}.json

# Detailed reports
GET https://protondb.max-p.me/games/{steam_appid}/reports
```

### Python Integration
```python
import httpx

r = httpx.get(f"https://www.protondb.com/api/v1/reports/summaries/{appid}.json")
data = r.json()
tier = data.get("tier")  # "platinum", "gold", etc.
total_reports = data.get("total")
confidence = data.get("confidence")
```

### Practical Assessment
**LOW EFFORT, MEDIUM VALUE.** Simple JSON endpoint, no auth needed. ProtonDB tier is a proxy for technical quality and Steam Deck compatibility -- increasingly important for market reach.

---

## 9. IsThereAnyDeal

### Status: Official API -- Documented

| Field | Detail |
|-------|--------|
| URL | `https://api.isthereanydeal.com/` |
| Docs | https://docs.isthereanydeal.com/ |
| Auth | API key (free registration) |
| Rate Limits | Not publicly documented; reasonable use expected |
| Format | JSON |
| Legal | Official API with terms |

### Key Endpoints
```
GET /games/prices/v3?key={key}&ids={game_ids}
    -- Current prices + historical low across all stores
GET /games/search/v1?key={key}&title={name}
    -- Search by game name
GET /games/info/v2?key={key}&id={game_id}
    -- Game metadata
```

### Data Available
- **Current price** across 30+ stores
- **Historical low** (all-time, 1 year, 3 months)
- **Discount percentage**
- **Bundle history**
- Webhook support for price alerts

### Practical Assessment
**MEDIUM PRIORITY.** Price history reveals business strategy:
- Games that never discount = confidence in value
- Frequent deep discounts = struggling retention
- Historical low timing = marketing cycle patterns

---

## 10. CheapShark

### Status: Free Public API -- No Auth Required

| Field | Detail |
|-------|--------|
| URL | `https://www.cheapshark.com/api/1.0/` |
| Docs | https://apidocs.cheapshark.com/ |
| Auth | None |
| Rate Limits | Reasonable use (undocumented) |
| Format | JSON |
| Legal | Free for use |

### Key Endpoints
```
GET /deals?title={name}&sortBy=Rating
GET /games?title={name}&limit=5
GET /games?id={cheapshark_id}   -- includes price history
GET /stores                     -- list of supported stores
```

### Data Available
- Current deals across multiple stores
- Price history per game
- **Deal rating** (CheapShark's calculated value score)
- Metacritic score (embedded in deal data)
- Steam AppID mapping

### Practical Assessment
**LOW EFFORT COMPLEMENT to IsThereAnyDeal.** No auth needed. Good for quick price context. CheapShark's deal rating is a unique "value" metric.

---

## 11. SteamSpy

### Status: Public API -- Rate Limited

| Field | Detail |
|-------|--------|
| URL | `https://steamspy.com/api.php` |
| Docs | https://steamspy.com/api.php (self-documented) |
| Auth | None |
| Rate Limits | 1 request per 60 seconds for "all" endpoint; lighter for individual |
| Format | JSON |
| Legal | Public API |

### Key Endpoints
```
GET ?request=appdetails&appid={appid}
GET ?request=genre&genre={genre}
GET ?request=tag&tag={tag}
GET ?request=top100in2weeks
GET ?request=top100forever
```

### Data Available Per Game
- **Owners** estimate with margin of error (e.g., "7,000,000 +/- 200,000")
- **Players in 2 weeks** / **Players forever**
- **Average playtime** (2 weeks / forever)
- **Median playtime** (2 weeks / forever)
- **CCU** (concurrent users estimate)
- **Price, score, tags**

### Python Library
- **steamspypi** (`pip install steamspypi`)

```python
import steamspypi

data = steamspypi.download({"request": "appdetails", "appid": "1145360"})
print(data["owners"])           # "5,000,000 .. 10,000,000"
print(data["average_forever"])  # average playtime in minutes
print(data["ccu"])              # peak concurrent users
```

### Practical Assessment
**RECOMMENDED.** Owner estimates and playtime data are invaluable for business analysis. Average vs median playtime reveals engagement distribution. Already used in some existing datasets (steam-insights GitHub).

---

## 12. GiantBomb API

### Status: Official Free API

| Field | Detail |
|-------|--------|
| URL | `https://www.giantbomb.com/api/` |
| Docs | https://www.giantbomb.com/api/documentation/ |
| Auth | Free API key (account required) |
| Rate Limits | 200 requests/hour (per resource) |
| Format | JSON/XML |
| Legal | Official, non-commercial use |

### Key Endpoints
```
GET /search/?api_key={key}&query={name}&resources=game&format=json
GET /game/{guid}/?api_key={key}&format=json
GET /reviews/?api_key={key}&filter=game:{guid}&format=json
```

### Data Available
- Game metadata (description, release date, platforms)
- **Concepts** (game mechanics taxonomy -- unique to GiantBomb)
- **Reviews** with full text + score (1-5 stars)
- **Similar games** list
- **Franchises, characters, objects** relationships

### Python Library
- **pybomb** (`pip install pybomb`)

### Practical Assessment
**MEDIUM PRIORITY.** GiantBomb's "Concepts" system is a unique game mechanics taxonomy not available elsewhere. Their review scores add another critic data point. 200 req/hr is decent.

---

## 13. Gaming News RSS Feeds

### Available Feeds

| Source | RSS URL | Focus |
|--------|---------|-------|
| GameSpot | `https://www.gamespot.com/feeds/mashup/` | Reviews + News |
| GameSpot Reviews | `https://www.gamespot.com/feeds/reviews/` | Reviews only |
| PC Gamer | `https://www.pcgamer.com/rss/` | PC gaming |
| Rock Paper Shotgun | `https://www.rockpapershotgun.com/feed` | PC, indie focus |
| Eurogamer | `https://www.eurogamer.net/feed` | European perspective |
| Kotaku | `https://kotaku.com/rss` | Cultural commentary |
| Game Informer | `https://gameinformer.com/rss` | Traditional reviews |
| Destructoid | `https://www.destructoid.com/feed/` | Reviews + opinion |
| Polygon | `https://www.polygon.com/rss/index.xml` | Culture + reviews |
| Ars Technica Gaming | `https://arstechnica.com/tag/gaming/feed/` | Tech-focused |

### Python Integration
```python
import feedparser

feed = feedparser.parse("https://www.gamespot.com/feeds/reviews/")
for entry in feed.entries:
    print(entry.title, entry.link, entry.published)
```

### Practical Assessment
**LOW PRIORITY for enrichment.** RSS feeds provide article links, not structured scores. Useful for:
- Detecting when a game gets press coverage (buzz indicator)
- Counting mentions across outlets (media attention metric)
- Would require NLP to extract sentiment/scores from article text

---

## 14. Korean Gaming Sources (한국 게임 평가)

### Status: No APIs -- Web Scraping Only

| Source | URL | Content |
|--------|-----|---------|
| 루리웹 (Ruliweb) | `https://ruliweb.com/` | Largest Korean gaming community; user reviews, ratings |
| 인벤 (Inven) | `https://www.inven.co.kr/` | Game-specific communities, news |
| 디시인사이드 게임 갤러리 | `https://gall.dcinside.com/` | Anonymous forum, raw user sentiment |
| GRAC (게임물관리위원회) | `https://www.grac.or.kr/` | Official Korean game ratings |

### 루리웹 (Ruliweb) Details
- Game pages with user scores (1-10)
- Review boards per game
- No API; requires HTML scraping
- Past scraping attempts used Node.js + Cheerio
- Anti-scraping measures: unknown severity

### 인벤 (Inven)
- Game-specific sub-communities
- News articles with reader comments
- No API documented
- Heavy JavaScript rendering (likely needs Playwright)

### GRAC (Official Ratings)
- Korean age rating data
- Searchable database on their website
- Public data for games reviewed in Korea

### Practical Assessment
**LOW PRIORITY.** No APIs, legal uncertainty, language-specific content. Best approach:
1. For Korean market sentiment: focus on Steam reviews filtered by `language=koreana` (already supported by our crawler)
2. GRAC data is niche but could be scraped for age rating information
3. Only pursue if Korean market analysis becomes a specific requirement

---

## 15. Additional Sources Worth Noting

### Game Data Crunch
- URL: https://www.gamedatacrunch.com/
- Aggregates SteamSpy, IGDB, RAWG, OpenCritic data
- Python package: `gamedatacrunch` (currently inactive maintenance)
- Useful methodology reference: https://www.gamedatacrunch.com/method

### Kaggle Datasets
- HowLongToBeat completion times: https://www.kaggle.com/datasets/kasumil5x/howlongtobeat-games-completion-times
- Steam games dataset (27K games): FronkonGames/steam-games-dataset on HuggingFace
- Good for historical analysis / ML training, not real-time enrichment

### Wikidata
- Structured game data linked to PCGamingWiki, IGDB, Steam
- SPARQL queries for cross-referencing
- Free, no auth, comprehensive linking

---

## Recommended Implementation Phases

### Phase 1: Quick Wins (1-2 days each)
1. **ProtonDB** -- single HTTP GET per appid, no auth, JSON response
2. **HowLongToBeat** -- `howlongtobeatpy` library, game length data
3. **SteamSpy** -- owner estimates + playtime, `steamspypi` library
4. **CheapShark** -- deal rating + price data, no auth

### Phase 2: High-Value APIs (2-3 days each)
5. **OpenCritic** -- critic scores + review excerpts (RapidAPI key needed)
6. **PCGamingWiki** -- technical quality data (Cargo API queries)
7. **YouTube Data API** -- review video metadata (Google API key needed)

### Phase 3: Extended Enrichment
8. **IGDB Extension** -- add `aggregated_rating`, `follows`, `hypes` to existing step1d
9. **IsThereAnyDeal** -- price history + deal patterns
10. **Reddit** -- community discussion threads
11. **GiantBomb** -- concepts taxonomy + reviews

### Phase 4: Optional / Research
12. **Gaming RSS Feeds** -- media coverage tracking
13. **Korean Sources** -- if Korean market analysis required

---

## Schema Design Considerations

### New DB Columns (per phase)

**Phase 1:**
```sql
-- ProtonDB
protondb_tier TEXT,              -- "platinum"/"gold"/"silver"/"bronze"/"borked"
protondb_confidence TEXT,         -- "good"/"moderate"/"low"
protondb_trending_tier TEXT,
protondb_report_count INTEGER,

-- HowLongToBeat
hltb_main_story REAL,           -- hours
hltb_main_extra REAL,
hltb_completionist REAL,
hltb_id INTEGER,

-- SteamSpy
steamspy_owners TEXT,            -- "5,000,000 .. 10,000,000"
steamspy_avg_playtime INTEGER,   -- minutes (forever)
steamspy_median_playtime INTEGER,
steamspy_ccu INTEGER,

-- CheapShark
cheapshark_deal_rating REAL,
cheapshark_lowest_price REAL,
```

**Phase 2:**
```sql
-- OpenCritic
opencritic_id INTEGER,
opencritic_score REAL,           -- 0-100
opencritic_pct_recommend REAL,   -- percentage
opencritic_tier TEXT,            -- "Mighty"/"Strong"/"Fair"/"Weak"
opencritic_review_count INTEGER,

-- PCGamingWiki
pcgw_engine TEXT,
pcgw_has_ultrawide INTEGER,      -- boolean
pcgw_has_hdr INTEGER,
pcgw_has_controller INTEGER,
pcgw_graphics_api TEXT,          -- "DirectX 12"/"Vulkan"

-- YouTube
yt_review_count INTEGER,
yt_top_review_views INTEGER,
yt_avg_review_score REAL,        -- computed from like ratio
yt_last_fetched TIMESTAMP,
```

### Alternative: Separate Tables
For sources with multiple records per game (YouTube videos, Reddit threads, OpenCritic reviews), consider separate tables:
```sql
CREATE TABLE external_reviews (
    id INTEGER PRIMARY KEY,
    appid INTEGER REFERENCES games(appid),
    source TEXT,          -- "opencritic"/"youtube"/"reddit"/"giantbomb"
    source_id TEXT,
    title TEXT,
    score REAL,
    author TEXT,
    outlet TEXT,
    url TEXT,
    view_count INTEGER,
    like_ratio REAL,
    published_at TIMESTAMP,
    fetched_at TIMESTAMP
);
```

---

## Environment Variables Needed

```env
# Already have (IGDB/Twitch)
TWITCH_CLIENT_ID=
TWITCH_CLIENT_SECRET=

# Phase 1 -- no new keys needed

# Phase 2
RAPIDAPI_KEY=              # OpenCritic
GOOGLE_API_KEY=            # YouTube Data API v3

# Phase 3
ITAD_API_KEY=              # IsThereAnyDeal
REDDIT_CLIENT_ID=          # Reddit OAuth2
REDDIT_CLIENT_SECRET=
GIANTBOMB_API_KEY=

# Phase 2 (RAWG already present)
RAWG_API_KEY=              # Already configured
```

---

## Sources

- [OpenCritic API on RapidAPI](https://rapidapi.com/opencritic-opencritic-default/api/opencritic-api)
- [OpenCritic API Terms of Use](https://c.opencritic.com/OpenCriticAPIAgreement.pdf)
- [YouTube Data API v3 Docs](https://developers.google.com/youtube/v3/docs)
- [YouTube API Quota Calculator](https://developers.google.com/youtube/v3/determine_quota_cost)
- [Reddit API Tools for 2026](https://painonsocial.com/blog/reddit-api-tools-2)
- [Reddit API Rate Limits](https://data365.co/blog/reddit-api-limits)
- [Arctic Shift (Reddit Archive)](https://github.com/ArthurHeitmann/arctic_shift)
- [HowLongToBeat Python API](https://github.com/ScrappyCocco/HowLongToBeat-PythonAPI)
- [howlongtobeatpy on PyPI](https://pypi.org/project/howlongtobeatpy/)
- [PCGamingWiki API](https://www.pcgamingwiki.com/wiki/PCGamingWiki:API)
- [ProtonDB Community API](https://protondb.max-p.me/)
- [ProtonDB Community API (GitHub)](https://github.com/Trsnaqe/protondb-community-api)
- [IsThereAnyDeal API Docs](https://docs.isthereanydeal.com/)
- [CheapShark API Docs](https://apidocs.cheapshark.com/)
- [Giant Bomb API Documentation](https://www.giantbomb.com/api/documentation/)
- [SteamSpy API](https://steamspy.com/api.php)
- [SteamSpyPI Python](https://github.com/woctezuma/steamspypi)
- [IGDB API Docs](https://api-docs.igdb.com/)
- [Metacritic Scraper (Apify)](https://apify.com/automation-lab/metacritic-scraper)
- [pycritic (GitHub)](https://github.com/ig3io/pycritic)
- [Metacritic Scraping Guide 2026](https://scraperly.com/scrape/metacritic)
- [Game Datasets (GitHub)](https://github.com/leomaurodesenv/game-datasets)
- [GameSpot RSS Feeds](https://www.gamespot.com/feeds/)
- [Top Video Game RSS Feeds](https://rss.feedspot.com/video_game_rss_feeds/)
- [Game Data Crunch Methodology](https://www.gamedatacrunch.com/method)
