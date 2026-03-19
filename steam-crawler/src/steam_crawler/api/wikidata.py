"""Wikidata SPARQL client — structured game design data."""

from __future__ import annotations

from steam_crawler.api.base import BaseClient
from steam_crawler.api.rate_limiter import AdaptiveRateLimiter

DESIGN_PROPERTIES = {
    "P136": "genre",
    "P4151": "mechanic",
    "P674": "character",
    "P840": "location",
    "P180": "depicts",
    "P404": "game_mode",
    "P479": "input_device",
    "P1552": "characteristic",
    "P166": "award",
    "P1411": "nominated",
}


class WikidataClient(BaseClient):
    """Fetches game design data from Wikidata SPARQL endpoint."""

    SPARQL_URL = "https://query.wikidata.org/sparql"

    def __init__(self, rate_limiter: AdaptiveRateLimiter | None = None):
        super().__init__(rate_limiter=rate_limiter, timeout=30.0)
        self._headers = {
            "Accept": "application/json",
            "User-Agent": "steam-game-analyzer/1.0 (game design research)",
        }

    def fetch_by_steam_appid(self, appid: int) -> dict | None:
        """Fetch all design-relevant claims for a Steam game by AppID.

        Returns dict with wikidata_id and claims list, or None if not found.
        Raises on HTTP errors so callers can log them properly.
        """
        prop_values = " ".join(f"wdt:{pid}" for pid in DESIGN_PROPERTIES)

        query = f'''
        SELECT ?game ?gameLabelKo ?prop ?val ?valLabel WHERE {{
          ?game wdt:P1733 "{appid}" .
          ?game ?prop ?val .
          VALUES ?prop {{ {prop_values} }}
          ?property wikibase:directClaim ?prop .
          OPTIONAL {{ ?game rdfs:label ?gameLabelKo . FILTER(LANG(?gameLabelKo) = "ko") }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" }}
        }}
        '''

        response = self.get(
            self.SPARQL_URL,
            params={"format": "json", "query": query},
            headers=self._headers,
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"Wikidata SPARQL HTTP {response.status_code} for appid={appid}"
            )

        data = response.json()
        bindings = data.get("results", {}).get("bindings", [])

        if not bindings:
            return None

        game_uri = bindings[0].get("game", {}).get("value", "")
        wikidata_id = game_uri.split("/")[-1] if game_uri else None
        name_ko = bindings[0].get("gameLabelKo", {}).get("value") or None

        claims = []
        for row in bindings:
            prop_uri = row.get("prop", {}).get("value", "")
            pid = prop_uri.split("/")[-1]
            claim_type = DESIGN_PROPERTIES.get(pid, pid)

            val_uri = row.get("val", {}).get("value", "")
            val_qid = val_uri.split("/")[-1] if "/entity/" in val_uri else None
            val_label = row.get("valLabel", {}).get("value", val_qid or "")

            claims.append({
                "claim_type": claim_type,
                "name": val_label,
                "wikidata_id": val_qid,
                "property_id": pid,
            })

        return {
            "wikidata_id": wikidata_id,
            "name_ko": name_ko,
            "claims": claims,
        }
