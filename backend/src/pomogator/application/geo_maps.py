"""Hydrate geo_map blocks from a public map source during sync."""

from __future__ import annotations

import logging
from typing import Any, Protocol

from pomogator.domain.geo_map import GeoMapData, lift_geo_map_blocks

log = logging.getLogger(__name__)


class GeoMapFetcher(Protocol):
    async def fetch(self, engine: str, map_id: str) -> GeoMapData: ...


async def hydrate_geo_maps(
    document: list[dict[str, Any]], fetcher: GeoMapFetcher
) -> list[dict[str, Any]]:
    lifted = lift_geo_map_blocks(document)
    output: list[dict[str, Any]] = []
    for block in lifted:
        if block.get("type") != "geo_map":
            output.append(block)
            continue
        engine = str(block.get("engine") or "")
        map_id = str(block.get("map_id") or "")
        if not engine or not map_id:
            output.append(block)
            continue
        try:
            data = await fetcher.fetch(engine, map_id)
        except Exception:
            log.exception("Failed to fetch geo map %s:%s", engine, map_id)
            output.append(block)
            continue
        output.append({"type": "geo_map", **data.as_block_payload()})
    return output
