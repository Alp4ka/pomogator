from collections.abc import Awaitable, Callable
from pathlib import Path

from pomogator.application.geo_maps import hydrate_geo_maps
from pomogator.domain.fields import annotate_document_fields
from pomogator.domain.geo_map import (
    GeoLayer,
    GeoMapData,
    GeoPlace,
    google_directions_url,
    google_place_url,
    lift_geo_map_blocks,
    parse_geo_map_tag,
)
from pomogator.infrastructure.geo.google_mymaps import kml_color_to_hex, parse_google_kml

_FIXTURE = Path(__file__).parent / "fixtures" / "geo_map_sample.kml"


def test_parse_geo_map_tag_normalizes_engine():
    ref = parse_geo_map_tag("{pmg.field.geo_map(google, 1gI16mMa1iau2Qle6FOXbKf8kDBU3f6Q)}")
    assert ref is not None
    assert ref.engine == "google"
    assert ref.map_id == "1gI16mMa1iau2Qle6FOXbKf8kDBU3f6Q"
    assert parse_geo_map_tag("{pmg.field.geo_map(gmaps, abc)}") == parse_geo_map_tag(
        "{pmg.field.geo_map(GOOGLE_MAPS, abc)}"
    )
    assert parse_geo_map_tag("{pmg.field.geo_map(bing, abc)}") is None
    assert parse_geo_map_tag("карта {pmg.field.geo_map(google, abc)}") is None


def test_lift_solo_paragraph_into_geo_map_block():
    document = [
        {
            "type": "paragraph",
            "rich_text": [
                {"text": "{pmg.field.geo_map(google, 1gI16mMa1iau2Qle6FOXbKf8kDBU3f6Q)}"}
            ],
        },
        {"type": "paragraph", "rich_text": [{"text": "рядом"}]},
    ]
    lifted = lift_geo_map_blocks(document)
    assert lifted[0]["type"] == "geo_map"
    assert lifted[0]["engine"] == "google"
    assert lifted[0]["map_id"] == "1gI16mMa1iau2Qle6FOXbKf8kDBU3f6Q"
    assert lifted[1]["type"] == "paragraph"


def test_parse_google_kml_fixture():
    data = parse_google_kml(_FIXTURE.read_text(encoding="utf-8"), engine="google", map_id="mid-1")
    assert data.title == "Полезные места"
    assert data.description == "Тестовая карта"
    assert [layer.name for layer in data.layers] == ["Медицина", "Пляжи"]
    assert data.layers[0].color == "#0288D1"
    assert data.layers[0].count == 1
    assert len(data.places) == 2
    hospital = data.places[0]
    assert hospital.name == "Hospital Nova Esperança"
    assert hospital.lat == -7.130032
    assert hospital.lng == -34.874236
    assert hospital.layer == "Медицина"
    assert hospital.color == "#0288D1"
    assert kml_color_to_hex("ffd18802") == "#0288D1"


def test_google_urls():
    assert google_place_url(-7.13, -34.87).startswith("https://www.google.com/maps/search/")
    assert "destination=-7.130000,-34.870000" in google_directions_url(-7.13, -34.87)


class _Fetcher:
    def __init__(self, impl: Callable[[str, str], Awaitable[GeoMapData]]) -> None:
        self._impl = impl

    async def fetch(self, engine: str, map_id: str) -> GeoMapData:
        return await self._impl(engine, map_id)


async def test_hydrate_geo_maps_fills_places():
    async def fetch(engine: str, map_id: str) -> GeoMapData:
        assert engine == "google"
        assert map_id == "mid-1"
        return GeoMapData(
            engine=engine,
            map_id=map_id,
            title="Город",
            description="",
            layers=[GeoLayer(name="Пляжи", color="#FFD600", count=1)],
            places=[
                GeoPlace(
                    id="beach",
                    name="Tambaú",
                    lat=-7.11,
                    lng=-34.82,
                    layer="Пляжи",
                    color="#FFD600",
                )
            ],
        )

    document = await hydrate_geo_maps(
        [
            {
                "type": "paragraph",
                "rich_text": [{"text": "{pmg.field.geo_map(google, mid-1)}"}],
            }
        ],
        _Fetcher(fetch),
    )
    block = document[0]
    assert block["type"] == "geo_map"
    assert block["title"] == "Город"
    assert block["places"][0]["name"] == "Tambaú"


async def test_hydrate_keeps_block_when_fetch_fails():
    async def fetch(_engine: str, _map_id: str) -> GeoMapData:
        raise RuntimeError("down")

    document = await hydrate_geo_maps(
        [
            {
                "type": "paragraph",
                "rich_text": [{"text": "{pmg.field.geo_map(google, mid-1)}"}],
            }
        ],
        _Fetcher(fetch),
    )
    assert document[0]["type"] == "geo_map"
    assert document[0]["places"] == []


def test_annotate_lifts_solo_tag_and_keeps_hydrated_block():
    annotated, specs = annotate_document_fields(
        [
            {
                "type": "paragraph",
                "rich_text": [{"text": "{pmg.field.geo_map(google, mid-1)}"}],
            },
            {
                "type": "paragraph",
                "rich_text": [{"text": "Смотри {pmg.field.geo_map(google, mid-1)}"}],
            },
            {
                "type": "geo_map",
                "engine": "google",
                "map_id": "mid-1",
                "title": "Город",
                "places": [
                    {"id": "1", "name": "Пляж", "lat": -7.1, "lng": -34.8, "layer": "Пляжи"}
                ],
            },
        ]
    )
    assert specs == {}
    assert annotated[0]["type"] == "geo_map"
    assert annotated[0]["map_id"] == "mid-1"
    assert annotated[0]["places"] == []
    assert annotated[1]["type"] == "paragraph"
    assert annotated[1]["runs"][1] == {"type": "geo_map", "engine": "google", "map_id": "mid-1"}
    assert annotated[2]["title"] == "Город"
    assert annotated[2]["places"][0]["name"] == "Пляж"
