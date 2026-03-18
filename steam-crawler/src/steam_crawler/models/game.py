"""Game data models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class GameSummary:
    appid: int
    name: str
    positive: int | None = None
    negative: int | None = None
    owners: str | None = None
    price: int | None = None
    tags: dict[str, int] | None = None
    avg_playtime: int | None = None
    score_rank: str | None = None
    source_tag: str | None = None

    @classmethod
    def from_steamspy(cls, data: dict[str, Any], source_tag: str | None = None) -> GameSummary:
        tags_raw = data.get("tags")
        tags = tags_raw if isinstance(tags_raw, dict) else None

        price_raw = data.get("price")
        price = int(price_raw) if price_raw is not None else None

        return cls(
            appid=int(data["appid"]),
            name=data["name"],
            positive=data.get("positive"),
            negative=data.get("negative"),
            owners=data.get("owners"),
            price=price,
            tags=tags,
            avg_playtime=data.get("average_forever"),
            score_rank=data.get("score_rank") or None,
            source_tag=source_tag,
        )
