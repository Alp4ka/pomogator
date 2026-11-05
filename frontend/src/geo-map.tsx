import { useMemo, useState } from "react";

import { Icon, pickIcon, type IconName } from "./icons";

export type GeoPlace = {
  id: string;
  name: string;
  lat: number;
  lng: number;
  layer: string;
  color?: string;
};

export type GeoLayer = {
  name: string;
  color: string;
  count: number;
};

export type GeoMapBlock = {
  engine: string;
  map_id: string;
  title?: string;
  description?: string;
  source_url?: string;
  layers?: GeoLayer[];
  places?: GeoPlace[];
};

const FALLBACK_COLORS = ["#e24b4b", "#e3a008", "#3f4a55", "#2f9a57", "#0288d1", "#9c27b0"];

type LayerLook = { icon: IconName; color: string; short: string };

function layerLook(name: string): LayerLook {
  const icon = pickIcon(name);
  if (/медиц|больниц|здоров|врач|родд/i.test(name)) {
    return { icon: "plus", color: "#e24b4b", short: "Больницы" };
  }
  if (/кафе|ресторан|еда/i.test(name)) {
    return { icon: "cafe", color: "#e3a008", short: "Кафе" };
  }
  if (/парк|пляж|прогул|зелен/i.test(name)) {
    return { icon: "tree", color: "#2f9a57", short: "Парки" };
  }
  if (/магазин|торгов/i.test(name)) {
    return { icon: "cart", color: "#0288d1", short: "Магазины" };
  }
  if (/детск|развлеч/i.test(name)) {
    return { icon: "baby", color: "#9c27b0", short: "Детям" };
  }
  if (/достопримеч|музей|обзор/i.test(name)) {
    return { icon: "camera", color: "#3f4a55", short: "Места" };
  }
  return { icon, color: FALLBACK_COLORS[0] ?? "#e24b4b", short: name };
}

function googlePlaceUrl(place: GeoPlace): string {
  return `https://www.google.com/maps/search/?api=1&query=${place.lat.toFixed(6)},${place.lng.toFixed(6)}`;
}

function googleDirectionsUrl(place: GeoPlace): string {
  return `https://www.google.com/maps/dir/?api=1&destination=${place.lat.toFixed(6)},${place.lng.toFixed(6)}`;
}

function googleMyMapsEmbed(mapId: string, place?: GeoPlace | null): string {
  const params = new URLSearchParams({
    mid: mapId,
    ehbc: "FFFFFF",
    z: place ? "16" : "13",
  });
  if (place) params.set("ll", `${place.lat},${place.lng}`);
  return `https://www.google.com/maps/d/embed?${params.toString()}`;
}

function itemWash(color: string): string {
  return `color-mix(in srgb, ${color} 16%, var(--card))`;
}

export function GeoMapCard({ map }: { map: GeoMapBlock }) {
  const places = useMemo(
    () => (map.places ?? []).filter((place) => Number.isFinite(place.lat) && Number.isFinite(place.lng)),
    [map.places],
  );
  const legend = useMemo(() => {
    const names = (map.layers ?? []).map((layer) => layer.name);
    const source = names.length ? names : [...new Set(places.map((place) => place.layer))];
    return source.filter(Boolean).map((name) => ({ name, ...layerLook(name) }));
  }, [map.layers, places]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [overview, setOverview] = useState(true);
  const selected = places.find((place) => place.id === selectedId) ?? places[0] ?? null;
  const selectedLook = selected ? layerLook(selected.layer) : null;
  const embedSrc = map.map_id
    ? googleMyMapsEmbed(map.map_id, overview ? null : selected)
    : "";

  function focusPlace(place: GeoPlace) {
    setSelectedId(place.id);
    setOverview(false);
  }

  if (!map.map_id && !places.length) {
    return (
      <section className="geo-card">
        <h3 className="geo-card-title">Карта города</h3>
        <p className="geo-card-empty">Нажмите «Обновить», чтобы загрузить карту из Google Maps.</p>
      </section>
    );
  }

  return (
    <section className="geo-card">
      <h3 className="geo-card-title">Карта города</h3>
      {embedSrc ? (
        <div className="geo-map-frame">
          <iframe
            className="geo-map-frame-embed"
            src={embedSrc}
            title={map.title || "Карта города"}
            referrerPolicy="no-referrer-when-downgrade"
            allowFullScreen
          />
          {!overview && selected ? (
            <button type="button" className="geo-compass" aria-label="Показать всю карту" onClick={() => setOverview(true)}>
              <Icon name="plane" />
            </button>
          ) : null}
        </div>
      ) : (
        <p className="geo-card-empty">Нажмите «Обновить», чтобы загрузить карту из Google Maps.</p>
      )}
      {legend.length ? (
        <div className="geo-legend" role="list">
          {legend.map((item) => (
            <button
              key={item.name}
              type="button"
              className={`geo-legend-item ${selected?.layer === item.name ? "is-active" : ""}`}
              onClick={() => {
                const match = places.find((place) => place.layer === item.name);
                if (match) focusPlace(match);
              }}
            >
              <span className="geo-legend-icon" style={{ color: item.color }}>
                <Icon name={item.icon} />
              </span>
              {item.short}
            </button>
          ))}
        </div>
      ) : null}
      {selected && selectedLook ? (
        <div className="geo-spot">
          <a className="geo-spot-main" href={googlePlaceUrl(selected)} target="_blank" rel="noreferrer">
            <span className="geo-spot-badge" style={{ background: itemWash(selectedLook.color), color: selectedLook.color }}>
              <Icon name={selectedLook.icon} />
            </span>
            <span className="geo-spot-copy">
              <strong>{selected.name}</strong>
              <em>{selected.layer}</em>
            </span>
          </a>
          <a className="geo-spot-route" href={googleDirectionsUrl(selected)} target="_blank" rel="noreferrer">
            <Icon name="plane" />
            Построить маршрут
          </a>
        </div>
      ) : null}
    </section>
  );
}
