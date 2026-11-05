"""Fetch and parse a public Google My Maps KML export."""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from collections import Counter
from typing import Any

import httpx

from pomogator.domain.geo_map import GeoLayer, GeoMapData, GeoPlace
from pomogator.domain.sync_errors import NotionSyncError

_KML_NS = {"k": "http://www.opengis.net/kml/2.2"}
_KML_URL = "https://www.google.com/maps/d/kml"


def _text(node: ET.Element | None, path: str, default: str = "") -> str:
    if node is None:
        return default
    value = node.findtext(path, default=default, namespaces=_KML_NS)
    return (value or default).strip()


def kml_color_to_hex(value: str) -> str:
    raw = value.strip().lstrip("#")
    if len(raw) == 8:
        return f"#{raw[6:8]}{raw[4:6]}{raw[2:4]}".upper()
    if len(raw) == 6:
        return f"#{raw}".upper()
    return ""


def _collect_style_colors(document: ET.Element) -> dict[str, str]:
    colors: dict[str, str] = {}
    for style in document.findall("k:Style", _KML_NS):
        style_id = style.get("id")
        if not style_id:
            continue
        color = kml_color_to_hex(_text(style, "k:IconStyle/k:color"))
        if color:
            colors[f"#{style_id}"] = color
            colors[style_id] = color
    for style_map in document.findall("k:StyleMap", _KML_NS):
        map_id = style_map.get("id")
        if not map_id:
            continue
        for pair in style_map.findall("k:Pair", _KML_NS):
            if _text(pair, "k:key") != "normal":
                continue
            target = _text(pair, "k:styleUrl")
            color = colors.get(target, "")
            if color:
                colors[f"#{map_id}"] = color
                colors[map_id] = color
    return colors


def _parse_coordinates(raw: str) -> tuple[float, float] | None:
    token = raw.strip().split()[0] if raw.strip() else ""
    parts = token.split(",")
    if len(parts) < 2:
        return None
    try:
        lng = float(parts[0])
        lat = float(parts[1])
    except ValueError:
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
        return None
    return lat, lng


def _place_id(name: str, lat: float, lng: float) -> str:
    material = f"{name}\0{lat:.6f}\0{lng:.6f}".encode()
    return hashlib.sha256(material).hexdigest()[:16]


def parse_google_kml(xml_text: str, *, engine: str, map_id: str) -> GeoMapData:
    root = ET.fromstring(xml_text)
    found = root.find("k:Document", _KML_NS)
    document = found if found is not None else root
    colors = _collect_style_colors(document)
    title = _text(document, "k:name") or "Карта"
    description = _text(document, "k:description")
    places: list[GeoPlace] = []
    layer_colors: dict[str, str] = {}

    def walk(folder: ET.Element, layer: str) -> None:
        for child in folder.findall("k:Folder", _KML_NS):
            walk(child, _text(child, "k:name") or layer)
        for mark in folder.findall("k:Placemark", _KML_NS):
            name = _text(mark, "k:name")
            coords = _parse_coordinates(_text(mark, "k:Point/k:coordinates"))
            if coords is None or not name:
                continue
            lat, lng = coords
            color = colors.get(_text(mark, "k:styleUrl"), "")
            if color and layer not in layer_colors:
                layer_colors[layer] = color
            places.append(
                GeoPlace(
                    id=_place_id(name, lat, lng),
                    name=name,
                    lat=lat,
                    lng=lng,
                    layer=layer,
                    color=color or layer_colors.get(layer, ""),
                )
            )

    folders = document.findall("k:Folder", _KML_NS)
    if folders:
        for folder in folders:
            walk(folder, _text(folder, "k:name") or "Места")
    else:
        walk(document, "Места")

    counts = Counter(place.layer for place in places)
    layers = [
        GeoLayer(name=name, color=layer_colors.get(name, ""), count=counts[name])
        for name in dict.fromkeys(place.layer for place in places)
    ]
    return GeoMapData(
        engine=engine,
        map_id=map_id,
        title=title,
        description=description,
        layers=layers,
        places=places,
    )


class GoogleMyMapsClient:
    def __init__(self, http: httpx.AsyncClient):
        self.http = http

    async def fetch(self, engine: str, map_id: str) -> GeoMapData:
        if engine != "google":
            raise NotionSyncError("failed")
        response = await self.http.get(
            _KML_URL,
            params={"mid": map_id, "forcekml": "1"},
            headers={"Accept": "application/vnd.google-earth.kml+xml,text/xml,*/*"},
            follow_redirects=True,
        )
        if response.status_code >= 400 or not response.text.lstrip().startswith("<"):
            raise NotionSyncError("failed")
        return parse_google_kml(response.text, engine=engine, map_id=map_id)


def geo_map_from_block(block: dict[str, Any]) -> GeoMapData | None:
    engine = str(block.get("engine") or "")
    map_id = str(block.get("map_id") or "")
    if not engine or not map_id:
        return None
    places = []
    for raw in block.get("places") or []:
        if not isinstance(raw, dict):
            continue
        try:
            places.append(
                GeoPlace(
                    id=str(raw.get("id") or ""),
                    name=str(raw.get("name") or ""),
                    lat=float(raw["lat"]),
                    lng=float(raw["lng"]),
                    layer=str(raw.get("layer") or ""),
                    color=str(raw.get("color") or ""),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    layers = []
    for raw in block.get("layers") or []:
        if not isinstance(raw, dict):
            continue
        layers.append(
            GeoLayer(
                name=str(raw.get("name") or ""),
                color=str(raw.get("color") or ""),
                count=int(raw.get("count") or 0),
            )
        )
    return GeoMapData(
        engine=engine,
        map_id=map_id,
        title=str(block.get("title") or ""),
        description=str(block.get("description") or ""),
        layers=layers,
        places=places,
    )
