"""Google My Maps tags and the stored geo_map document block."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

_GEO_MAP_TAG = re.compile(
    r"\{pmg\.field\.geo_map\(\s*([A-Za-z0-9_-]+)\s*,\s*([A-Za-z0-9_-]+)\s*\)\}",
    re.IGNORECASE,
)
_SUPPORTED_ENGINES = {
    "google": "google",
    "gmaps": "google",
    "googlemaps": "google",
    "google_maps": "google",
    "google-maps": "google",
}


@dataclass(frozen=True, slots=True)
class GeoMapRef:
    engine: str
    map_id: str


@dataclass(frozen=True, slots=True)
class GeoPlace:
    id: str
    name: str
    lat: float
    lng: float
    layer: str
    color: str = ""


@dataclass(frozen=True, slots=True)
class GeoLayer:
    name: str
    color: str
    count: int


@dataclass(frozen=True, slots=True)
class GeoMapData:
    engine: str
    map_id: str
    title: str
    description: str
    layers: list[GeoLayer] = field(default_factory=list)
    places: list[GeoPlace] = field(default_factory=list)

    def as_block_payload(self) -> dict[str, Any]:
        return {
            "engine": self.engine,
            "map_id": self.map_id,
            "title": self.title,
            "description": self.description,
            "source_url": google_viewer_url(self.map_id),
            "layers": [
                {"name": layer.name, "color": layer.color, "count": layer.count}
                for layer in self.layers
            ],
            "places": [
                {
                    "id": place.id,
                    "name": place.name,
                    "lat": place.lat,
                    "lng": place.lng,
                    "layer": place.layer,
                    "color": place.color,
                }
                for place in self.places
            ],
        }


def geo_map_tag_pattern() -> re.Pattern[str]:
    return _GEO_MAP_TAG


def has_geo_map_tags(text: str) -> bool:
    return bool(_GEO_MAP_TAG.search(text))


def normalize_geo_engine(raw: str) -> str | None:
    key = raw.strip().casefold().replace(" ", "")
    return _SUPPORTED_ENGINES.get(key)


def parse_geo_map_tag(text: str) -> GeoMapRef | None:
    match = _GEO_MAP_TAG.fullmatch(text.strip())
    if not match:
        return None
    engine = normalize_geo_engine(match.group(1))
    map_id = match.group(2).strip()
    if engine is None or not map_id:
        return None
    return GeoMapRef(engine=engine, map_id=map_id)


def iter_geo_map_spans(text: str) -> list[tuple[int, int, GeoMapRef]]:
    spans: list[tuple[int, int, GeoMapRef]] = []
    for match in _GEO_MAP_TAG.finditer(text):
        engine = normalize_geo_engine(match.group(1))
        map_id = match.group(2).strip()
        if engine is None or not map_id:
            continue
        spans.append((match.start(), match.end(), GeoMapRef(engine=engine, map_id=map_id)))
    return spans


def google_viewer_url(map_id: str) -> str:
    return f"https://www.google.com/maps/d/viewer?mid={map_id}"


def google_place_url(lat: float, lng: float) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={lat:.6f},{lng:.6f}"


def google_directions_url(lat: float, lng: float) -> str:
    return f"https://www.google.com/maps/dir/?api=1&destination={lat:.6f},{lng:.6f}"


def _plain_from_rich(rich: object) -> str:
    if not isinstance(rich, list):
        return ""
    return "".join(str(part.get("text", "")) for part in rich if isinstance(part, dict))


def lift_geo_map_blocks(document: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn a paragraph that is only a geo_map tag into a geo_map block."""
    output: list[dict[str, Any]] = []
    for raw in document:
        block = dict(raw)
        if block.get("type") == "geo_map":
            output.append(block)
            continue
        if str(block.get("type") or "paragraph") != "paragraph":
            output.append(block)
            continue
        ref = parse_geo_map_tag(_plain_from_rich(block.get("rich_text")))
        if ref is None:
            output.append(block)
            continue
        lifted = {
            "type": "geo_map",
            "engine": ref.engine,
            "map_id": ref.map_id,
            "title": str(block.get("title") or ""),
            "description": str(block.get("description") or ""),
            "source_url": google_viewer_url(ref.map_id),
            "layers": list(block.get("layers") or []),
            "places": list(block.get("places") or []),
        }
        output.append(lifted)
    return output
