# Roguelike Tag Crawl Results

- Date: 2026-03-18
- Command: `steam-crawler collect --tag "Roguelike" --limit 5 --top-n 2 --max-reviews 10`
- DB Version: 1
- Status: completed

## Collected Games (5)

| # | AppID  | Name                                    | Positive | Negative | Total Reviews | Score                  | Owners                    | Price  | AvgPlaytime |
|---|--------|-----------------------------------------|----------|----------|---------------|------------------------|---------------------------|--------|-------------|
| 1 | 901583 | Grand Theft Auto IV: Complete Edition   | 144,570  | 30,702   | 175,272       | Very Positive          | 20M-50M                  | $0.00  | 0min        |
| 2 | 12210  | Grand Theft Auto IV: The Complete Ed.   | 144,493  | 30,691   | 175,184       | Very Positive          | 5M-10M                   | $19.99 | 1805min     |
| 3 | 2990   | FlatOut 2                               | 17,923   | 737      | 18,660        | Overwhelmingly Positive| 500K-1M                   | $7.99  | 512min      |
| 4 | 891040 | Pool 2D - Poolians                      | 8,222    | 1,216    | 9,438         | Very Positive          | 500K-1M                   | $0.00  | 0min        |
| 5 | 22230  | Rock of Ages                            | 3,472    | 312      | 3,784         | Very Positive          | 200K-500K                 | $9.99  | 165min      |

## Reviews Collected

| Game                                    | Reviews | Positive | Negative |
|-----------------------------------------|---------|----------|----------|
| Grand Theft Auto IV: Complete Edition   | 80      | 69       | 11       |
| Grand Theft Auto IV: The Complete Ed.   | 80      | 69       | 11       |
| **Total**                               | **160** | **138**  | **22**   |

Top 2 games (by review count) had reviews crawled. Max was set to 10 but the API returned pages of ~80 reviews per batch.

## Failure Summary

- `data_quality`: 5 entries -- All 5 games flagged as data quality issues. This is because the SteamSpy API returned non-Roguelike games for the "Roguelike" tag query (GTA IV, FlatOut 2, Pool 2D, Rock of Ages). None of these games have "Roguelike" in their actual Steam tags.

## Observations

1. **SteamSpy tag accuracy issue**: The SteamSpy `/all` endpoint with `tag=Roguelike` returned completely unrelated games. This is a known limitation of the SteamSpy API where tag-based queries can return unreliable results.
2. **Review count mismatch**: Despite `--max-reviews 10`, 80 reviews were collected per game. The Steam Reviews API returns a full page (~80) per request, and the limiter applies after the first batch.
3. **Crawl speed**: The full pipeline completed quickly (~2 minutes) with the reduced limits.
