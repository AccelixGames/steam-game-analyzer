# Research: Game Design Knowledge & Analysis Sources

> Date: 2026-03-19
> Goal: Find structured/scrapeable sources for game design knowledge — mechanics, postmortems, design patterns, design rationale — to enrich a game design analysis tool.

---

## 1. Game Design Postmortems & Dev Blogs

### 1a. GDC Vault
- **URL**: https://gdcvault.com/
- **Content**: Thousands of game design talks, postmortems (classic series: Doom, Fallout, Ultima Online, Elite)
- **API**: NO official API. Paywall for most content.
- **YouTube**: GDC YouTube channel has 1,700+ free talks — accessible via YouTube Data API v3
- **Transcripts**: Community project [GDC-Transcript](https://blog.chosenconcept.dev/posts/2023/04/0014-gdc-transcript/) used OpenAI Whisper to transcribe all public GDC YouTube videos. GitHub repo exists but may face takedown risk.
- **Data format**: Video (YouTube), PDF slides (some), no structured metadata
- **Enrichment potential**: HIGH — transcript search for game-specific design decisions, postmortem "what went right/wrong" extraction via NLP

### 1b. Game Developer (formerly Gamasutra)
- **URL**: https://www.gamedeveloper.com/
- **Archive**: Full magazine archive 1994-2013 available as free PDFs at https://gdcvault.com/gdmag and https://archive.org/details/game_developer_magazine
- **API**: NO API. Web articles scrapeable. PDF archive downloadable.
- **Content**: Monthly "Postmortem" columns (top 5 What Went Right / What Went Wrong), deep design articles
- **Data format**: PDFs (magazine), HTML (web articles), RSS feed available
- **Enrichment potential**: HIGH — postmortem columns are highly structured (5 right / 5 wrong), could be extracted from PDFs programmatically

### 1c. Developer Blogs with Design Insights
| Blog | URL | RSS | Focus |
|------|-----|-----|-------|
| Lost Garden (Daniel Cook) | https://lostgarden.com/ | Yes | Game design theory, skill atoms, game grammar |
| Raph Koster | https://www.raphkoster.com/ | raphkoster.com/feed | MMO design, game theory, "Theory of Fun" |
| Emily Short | https://emshort.blog/ | Yes | Narrative design, interactive fiction, storylets |
| Deconstructor of Fun | https://www.deconstructoroffun.com/ | Yes (podcast) | F2P game deconstructions, monetization |

- **API**: No APIs, but all have RSS feeds for monitoring
- **Enrichment potential**: MEDIUM — RSS for new content, historical articles scrapeable, but unstructured text

---

## 2. Game Design Analysis YouTube Channels

### Key Channels for Mechanical Analysis (not reviews)
| Channel | Focus | Subscribers |
|---------|-------|-------------|
| Game Maker's Toolkit (Mark Brown) | Level design, accessibility, mechanics deep-dives | 1M+ |
| Design Doc | Design pattern breakdowns | Large |
| Extra Credits | Game design theory, industry | Large |
| Adam Millard (The Architect of Games) | Game design philosophy | Large |
| GDC | Official conference talks | Large |

### Programmatic Access
- **YouTube Data API v3**: YES — fully supported
  - Search by channel ID + keywords
  - Get video metadata (title, description, tags, captions)
  - Auto-generated captions available for transcript extraction
  - 10,000 quota units/day (free tier)
  - `search.list` with `channelId` filter to get all videos from a specific channel
- **Data format**: JSON (API), SRT/VTT (captions)
- **Enrichment potential**: HIGH — cross-reference game titles in video titles/descriptions to find design analysis content for specific games. Extract transcripts for NLP analysis of design discussions.

---

## 3. Game Design Databases & Wikis

### 3a. BoardGameGeek (BGG)
- **URL**: https://boardgamegeek.com/
- **API**: YES — BGG XML API2 (https://boardgamegeek.com/wiki/page/BGG_XML_API2)
  - Free, no auth required
  - Returns XML with game mechanics, categories, designers, ratings
  - Rate limited but generous
- **Mechanics taxonomy**: ~50+ defined mechanics (Deck Building, Worker Placement, Area Control, etc.)
- **Data format**: XML
- **Enrichment potential**: MEDIUM-HIGH — mechanics taxonomy is transferable to video games. Many video games borrow board game mechanics. Could map BGG mechanics to Steam tags.

### 3b. TVTropes
- **URL**: https://tvtropes.org/
- **API**: NO official API (requested for years, never built)
- **Scraping tools**:
  - [tropescraper](https://github.com/rhgarcia/tropescraper) — Python scraper for films/tropes
  - [Tropology](https://github.com/ricardojmendez/tropology) — Clojure crawler -> PostgreSQL
  - [TvTroper dataset](https://huggingface.co/datasets/RyokoExtra/TvTroper) — Pre-scraped on HuggingFace
  - [DBTropes](https://ceur-ws.org/Vol-674/Paper62.pdf) — Linked data wrapper (academic)
- **Gaming sections**: Extensive — VideoGame namespace with mechanics tropes, narrative tropes, gameplay tropes
- **Data format**: Wiki markup (unstructured), but relationship graph extractable
- **Enrichment potential**: HIGH — trope-to-game mappings provide design pattern analysis. "This game uses X trope" is exactly the kind of design knowledge we want.

### 3c. MobyGames
- **URL**: https://www.mobygames.com/
- **API**: YES — REST API with JSON (https://www.mobygames.com/info/api/)
  - Free API key for non-commercial use
  - 720 requests/hour, 1/sec rate limit
  - Game metadata: genres, platforms, descriptions, credits, screenshots
- **Data**: 321,000+ games
- **Data format**: JSON
- **Enrichment potential**: MEDIUM — comprehensive game metadata, but limited design-specific data. Good for cross-referencing.

### 3d. Game UI Database
- **URL**: https://www.gameuidatabase.com/
- **API**: NO known API
- **Content**: 55,000+ screenshots, 1,700+ videos from 1,300+ games
- **Searchable by**: Screen type, HUD elements, color, controls, patterns
- **Data format**: Screenshots/videos with metadata tags
- **Enrichment potential**: LOW-MEDIUM — visual design reference, not easily integrated programmatically

### 3e. Game Design Wiki (Pattern Language)
- **URL**: https://www.ludism.org/gamedesign/
- **Content**: Collaborative wiki building a Pattern Language of Game Design
- **API**: NO (MediaWiki, could use MediaWiki API if hosted on it)
- **Enrichment potential**: LOW — small, not actively maintained

### 3f. Game Design Library
- **URL**: https://nightblade9.github.io/game-design-library/
- **Content**: Curated catalogue of game-design links (crafting systems, economy design, etc.)
- **Data format**: Static site (GitHub Pages), likely markdown source
- **Enrichment potential**: LOW — link aggregator, not primary source

---

## 4. Academic / Research Sources

### 4a. Semantic Scholar
- **URL**: https://www.semanticscholar.org/
- **API**: YES — free, well-documented (https://api.semanticscholar.org/api-docs/)
  - Paper search, citation graphs, abstracts, PDF links
  - 1,000 req/sec (unauthenticated, shared)
  - Bulk search endpoint recommended
  - Python client: `pip install semanticscholar`
- **Data format**: JSON
- **Query examples**: "game design mechanics", "game balance", "procedural generation", "player retention"
- **Enrichment potential**: HIGH — search for academic papers about specific game design topics, extract abstracts and citations. Could build a knowledge graph of game design research.

### 4b. DiGRA (Digital Games Research Association)
- **URL**: https://digra.org/
- **Journal**: ToDiGRA (https://todigra.org/) — open access
- **Digital Library**: Open access conference proceedings
- **API**: NO direct API, but papers indexed in Semantic Scholar
- **Data format**: PDFs
- **Enrichment potential**: MEDIUM — niche academic source, accessible through Semantic Scholar

### 4c. Google Scholar
- **API**: NO official API (Terms prohibit scraping)
- **Alternative**: Use Semantic Scholar or OpenAlex as proxies
- **Enrichment potential**: Use Semantic Scholar instead

### 4d. OpenAlex
- **URL**: https://openalex.org/
- **API**: YES — free, no auth, generous rate limits
- **Coverage**: 250M+ works from all academic fields
- **Enrichment potential**: MEDIUM — broader than Semantic Scholar, could supplement academic game design research

---

## 5. GDD (Game Design Document) References

### GitHub Repositories
| Repo | Content |
|------|---------|
| [awesome-game-design](https://github.com/Roobyx/awesome-game-design) | Curated list of public GDDs, tools, learning materials |
| [game-design-document](https://github.com/saeidzebardast/game-design-document) | GDD outline, template, examples |
| [Game-Design-Document-Resources](https://github.com/mikewesthad/Game-Design-Document-Resources) | Collection of GDD examples and templates |
| [gdd-template](https://github.com/JarateKing/gdd-template) | LaTeX GDD template |
| [GDDMarkdownTemplate](https://github.com/LazyHatGuy/GDDMarkdownTemplate) | Markdown GDD template |
| [GitHub Topic: game-design-document](https://github.com/topics/game-design-document) | 50+ repos tagged |

- **API**: GitHub API for repo discovery and content
- **Data format**: Markdown, LaTeX, PDF
- **Enrichment potential**: LOW-MEDIUM — templates useful for structuring our own output, but not a data source per se

---

## 6. Community Design Discussion

### 6a. Reddit
- **Subreddits**: r/gamedesign (273k members), r/truegaming, r/gamedev
- **API**: YES — Reddit API (https://support.reddithelp.com/hc/en-us/articles/14945211791892)
  - OAuth2 authentication required
  - JSON responses
  - Rate limited (as of 2023, paid for high-volume)
  - PRAW Python library available
- **Data format**: JSON (posts, comments, scores)
- **Enrichment potential**: MEDIUM — search for game-specific design discussions. r/gamedesign posts often analyze mechanics. Could extract "why was X designed this way" discussions.

### 6b. itch.io
- **URL**: https://itch.io/devlogs/postmortems
- **API**: YES — basic server-side API (https://itch.io/docs/api/overview)
  - Limited — mainly for game ownership verification
  - No jam/devlog API (requested on GitHub issues #872, #640)
- **Devlog postmortems**: Rich source of indie game design rationale
- **Data format**: HTML (devlogs), no structured API for devlogs
- **Enrichment potential**: MEDIUM — scrapeable devlog postmortems, especially from game jams where designers explain design rationale

---

## 7. Industry Tools & Frameworks

### 7a. MDA Framework (Mechanics-Dynamics-Aesthetics)
- **Paper**: Hunicke, LeBlanc, Zubek (2004) — freely available PDF
- **URL**: https://www.cs.northwestern.edu/~hunicke/MDA.pdf
- **No API** — it's a conceptual framework
- **Enrichment potential**: Use as an analytical lens. Could classify game features into M/D/A categories.

### 7b. Machinations.io
- **URL**: https://machinations.io/
- **What it does**: Browser-based game economy simulation, balance modeling, Monte Carlo simulations
- **API**: NO public API (SaaS tool)
- **Content**: Blog articles on game economy design
- **Enrichment potential**: LOW — tool, not data source. Blog articles scrapeable.

### 7c. Pattern Language for Game Design
- **URL**: https://patternlanguageforgamedesign.com/
- **Book**: Chris Barney's work applying Christopher Alexander's pattern language to games
- **Data format**: Book/web reference
- **Enrichment potential**: LOW-MEDIUM — conceptual framework, some patterns may be extractable

### 7d. Game Programming Patterns
- **URL**: https://gameprogrammingpatterns.com/
- **Content**: Free online book — programming patterns in games (State, Observer, Command, etc.)
- **Data format**: HTML (full book online)
- **Enrichment potential**: LOW — programming patterns, not design patterns

---

## 8. Game Economy / Monetization Design

### 8a. GameRefinery (Liftoff)
- **URL**: https://www.gamerefinery.com/
- **What**: Most comprehensive mobile game feature-level database (100,000+ games)
- **Taxonomy**: 3-layer hierarchy — Game Category > Genre > Subgenre, plus feature-level tagging
- **API**: NO public API (enterprise SaaS, pricing not public)
- **Content**: Blog with game deconstructions (Genshin Impact, Roblox, etc.)
- **Data format**: Proprietary database
- **Enrichment potential**: LOW (no API access) — blog articles scrapeable for mobile game design patterns

### 8b. Deconstructor of Fun
- **URL**: https://www.deconstructoroffun.com/
- **Content**: Blog + podcast deconstructing F2P game mechanics, monetization, meta-game loops
- **API**: NO — blog/podcast
- **RSS**: Yes
- **Enrichment potential**: MEDIUM — scrapeable blog posts analyzing specific games' economy and design

---

## 9. Narrative Design Sources

### 9a. IFDB (Interactive Fiction Database)
- **URL**: https://ifdb.org/
- **API**: YES — documented API available
- **Content**: 12,900+ game listings, 12,700+ reviews, 51,700+ ratings
- **Data format**: Structured game metadata + reviews
- **Enrichment potential**: LOW-MEDIUM — niche (text adventures/IF), but structured data on narrative mechanics

### 9b. Emily Short's Interactive Storytelling
- **URL**: https://emshort.blog/
- **Content**: Quality-based narrative, storylet design, dialogue systems, narrative structure theory
- **RSS**: Yes
- **Enrichment potential**: MEDIUM — definitive source for narrative design patterns (storylets, quality-based narrative, Ink scripting)

### 9c. Inkle Blog
- **URL**: https://www.inklestudios.com/blog/
- **Content**: Technical narrative design — dialogue systems, branching narrative implementation
- **Enrichment potential**: LOW — niche but high quality

---

## 10. Korean Game Design Sources

### 10a. NDC (Nexon Developers Conference)
- **URL**: https://ndc.nexon.com/
- **Content**: Annual conference (since 2007), 49+ sessions per year
- **Video**: Sessions available on YouTube
- **API**: NO — YouTube API for video access
- **Enrichment potential**: MEDIUM — Korean-language design talks, accessible via YouTube API + transcript extraction

### 10b. GDF (Game Design Forum on Inven)
- **URL**: https://gdf.inven.co.kr/
- **Content**: Korean game design analysis and discussion community
- **API**: NO
- **Enrichment potential**: LOW-MEDIUM — Korean-language design discussions, scrapeable

### 10c. Korean Game Media
| Source | URL | Content |
|--------|-----|---------|
| GameMeca | https://www.gamemeca.com/ | News, analysis articles |
| Inven | https://www.inven.co.kr/ | Game community, webzine |
| Namu Wiki | https://namu.wiki/ | Detailed Korean game wiki entries |

---

## 11. Linked Data / Knowledge Graphs

### 11a. Wikidata — Video Games Project
- **URL**: https://www.wikidata.org/wiki/Wikidata:WikiProject_Video_games
- **API**: YES — SPARQL endpoint (https://query.wikidata.org/)
  - Free, no auth
  - 100,000+ video games catalogued
- **Properties**: genre (P136), game mode (P404), game mechanics (Q107647829), platform, developer, publisher, narrative location, fictional universe
- **Data format**: RDF/JSON via SPARQL
- **Enrichment potential**: HIGH — structured linked data with game mechanics, genres, themes. Can query "all games with mechanic X" or "games in genre Y by developer Z". Free and comprehensive.

### Example SPARQL query (games with their mechanics):
```sparql
SELECT ?game ?gameLabel ?mechanic ?mechanicLabel WHERE {
  ?game wdt:P31 wd:Q7889 .        # instance of video game
  ?game wdt:P136 ?mechanic .       # genre/mechanic
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
} LIMIT 100
```

---

## Priority Ranking for Integration

### Tier 1 — High Value, Programmatic Access Available
| Source | Why | API |
|--------|-----|-----|
| **YouTube Data API** (GDC/GMTK channels) | Design analysis videos with transcripts | REST API, 10k quota/day |
| **Wikidata SPARQL** | Structured game mechanics/genres linked data | Free SPARQL endpoint |
| **Semantic Scholar** | Academic game design research | Free REST API |
| **BoardGameGeek XML API** | Mechanics taxonomy | Free XML API |
| **MobyGames API** | Comprehensive game metadata | Free API key |

### Tier 2 — High Value, Scraping Required
| Source | Why | Method |
|--------|-----|--------|
| **TVTropes** | Design pattern/trope-to-game mappings | Scraper tools exist, HuggingFace dataset |
| **Game Developer / Gamasutra archive** | Postmortem columns (structured format) | PDF parsing from archive.org |
| **GDC YouTube transcripts** | Design talk content | Whisper transcription / YouTube captions |
| **Reddit r/gamedesign** | Community design analysis | Reddit API (paid for volume) |
| **itch.io devlog postmortems** | Indie design rationale | HTML scraping |

### Tier 3 — Reference / Manual Integration
| Source | Why | Notes |
|--------|-----|-------|
| **GameRefinery** | Best mobile mechanics taxonomy | Enterprise only, no public API |
| **Lost Garden / Raph Koster blogs** | Design theory | RSS monitoring, manual curation |
| **Pattern Language for Game Design** | Design pattern framework | Conceptual, not data |
| **NDC (Korean)** | Korean game design talks | YouTube + Korean NLP |
| **MDA Framework** | Analytical framework | Apply as classification lens |

---

## Recommended Implementation Order

1. **Wikidata SPARQL** — easiest to integrate, structured, free, covers mechanics/genres/themes
2. **YouTube Data API** — search design analysis channels for game-specific content, extract transcripts
3. **Semantic Scholar API** — academic research on game design topics
4. **BoardGameGeek API** — mechanics taxonomy as a reference vocabulary
5. **TVTropes dataset** (HuggingFace) — pre-scraped trope-game mappings
6. **MobyGames API** — supplementary game metadata
7. **Game Developer archive** (PDF parsing) — postmortem extraction from magazine PDFs
