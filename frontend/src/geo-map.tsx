import { useEffect, useMemo, useRef, useState } from "react";

import { Icon, iconPath, pickIcon, type IconName } from "./icons";
import "maplibre-gl/dist/maplibre-gl.css";

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
const LIGHT_STYLE = "https://tiles.openfreemap.org/styles/liberty";
const DARK_STYLE = "https://tiles.openfreemap.org/styles/dark";

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

function readTheme(): "light" | "dark" {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

function pinElement(place: GeoPlace, look: LayerLook, onSelect: (place: GeoPlace) => void): HTMLButtonElement {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "geo-pin";
  button.dataset.placeId = place.id;
  button.style.setProperty("--pin", look.color);
  button.title = place.name;
  button.setAttribute("aria-label", place.name);
  const filled = look.icon === "pin" || look.icon === "heart" || look.icon === "home";
  button.innerHTML = `<span class="geo-pin-mark"><svg viewBox="0 0 24 24" fill="${filled ? "currentColor" : "none"}" stroke="currentColor" stroke-width="${filled ? 0 : 2}" stroke-linecap="round" stroke-linejoin="round"><path d="${iconPath(look.icon)}"></path></svg></span>`;
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    onSelect(place);
  });
  return button;
}

function restyleMap(map: import("maplibre-gl").Map, theme: "light" | "dark") {
  if (theme === "dark") return;
  for (const layer of map.getStyle().layers ?? []) {
    const id = layer.id.toLowerCase();
    try {
      if (layer.type === "background") map.setPaintProperty(layer.id, "background-color", "#f4f1ea");
      if (layer.type === "fill" && (id.includes("water") || id.includes("ocean"))) {
        map.setPaintProperty(layer.id, "fill-color", "#7ec8ea");
      }
      if (layer.type === "fill" && (id.includes("park") || id.includes("grass") || id.includes("wood"))) {
        map.setPaintProperty(layer.id, "fill-color", "#9fd67a");
      }
      if (layer.type === "fill" && id.includes("building")) {
        map.setPaintProperty(layer.id, "fill-color", "#efe6d6");
      }
    } catch {
      /* style layer without a solid color */
    }
  }
}

export function GeoMapCard({ map }: { map: GeoMapBlock }) {
  const places = useMemo(
    () => (map.places ?? []).filter((place) => Number.isFinite(place.lat) && Number.isFinite(place.lng)),
    [map.places],
  );
  const layers = useMemo(() => map.layers ?? [], [map.layers]);
  const legend = useMemo(() => {
    const names = layers.length ? layers.map((layer) => layer.name) : [...new Set(places.map((place) => place.layer))];
    return names.filter(Boolean).map((name) => ({ name, ...layerLook(name) }));
  }, [layers, places]);
  const hostRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<import("maplibre-gl").Map | null>(null);
  const pinRefs = useRef<Map<string, HTMLButtonElement>>(new Map());
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const selected = places.find((place) => place.id === selectedId) ?? places[0] ?? null;

  useEffect(() => {
    const host = hostRef.current;
    if (!host || !places.length) return;
    let cancelled = false;
    let observer: ResizeObserver | undefined;
    const pins = pinRefs.current;

    void import("maplibre-gl").then((mod) => {
      if (cancelled || !hostRef.current) return;
      const maplibre = mod.default;
      const theme = readTheme();
      host.dataset.theme = theme;
      const map = new maplibre.Map({
        container: host,
        style: theme === "dark" ? DARK_STYLE : LIGHT_STYLE,
        attributionControl: { compact: true },
        scrollZoom: false,
        dragRotate: false,
        pitchWithRotate: false,
        cooperativeGestures: false,
      });
      const bounds = new maplibre.LngLatBounds();
      pins.clear();
      for (const place of places) {
        const look = layerLook(place.layer);
        const element = pinElement(place, look, (next) => setSelectedId(next.id));
        new maplibre.Marker({ element, anchor: "bottom" }).setLngLat([place.lng, place.lat]).addTo(map);
        pins.set(place.id, element);
        bounds.extend([place.lng, place.lat]);
      }
      const fit = () => {
        restyleMap(map, theme);
        if (bounds.isEmpty()) return;
        map.fitBounds(bounds, { padding: 36, maxZoom: 12.2, duration: 0 });
      };
      if (map.loaded()) fit();
      else map.once("load", fit);
      observer = new ResizeObserver(() => map.resize());
      observer.observe(host);
      mapRef.current = map;
      map.once("idle", () => setReady(true));
    });

    return () => {
      cancelled = true;
      observer?.disconnect();
      mapRef.current?.remove();
      mapRef.current = null;
      pins.clear();
    };
  }, [places]);

  useEffect(() => {
    for (const [id, pin] of pinRefs.current) {
      pin.classList.toggle("is-active", selected?.id === id);
    }
  }, [selected, ready]);

  function focusPlace(place: GeoPlace) {
    setSelectedId(place.id);
    mapRef.current?.easeTo({ center: [place.lng, place.lat], duration: 380 });
  }

  function focusLayer(name: string) {
    const match = places.find((place) => place.layer === name);
    if (match) focusPlace(match);
  }

  function recenter() {
    const map = mapRef.current;
    if (!map || !places.length) return;
    let minLng = places[0]!.lng;
    let minLat = places[0]!.lat;
    let maxLng = minLng;
    let maxLat = minLat;
    for (const place of places) {
      minLng = Math.min(minLng, place.lng);
      minLat = Math.min(minLat, place.lat);
      maxLng = Math.max(maxLng, place.lng);
      maxLat = Math.max(maxLat, place.lat);
    }
    map.fitBounds(
      [
        [minLng, minLat],
        [maxLng, maxLat],
      ],
      { padding: 36, maxZoom: 12.2, duration: 400 },
    );
  }

  const selectedLook = selected ? layerLook(selected.layer) : null;

  if (!places.length) {
    return (
      <section className="geo-card">
        <h3 className="geo-card-title">Карта города</h3>
        <p className="geo-card-empty">Нажмите «Обновить», чтобы загрузить точки с Google Maps.</p>
      </section>
    );
  }

  return (
    <section className="geo-card">
      <h3 className="geo-card-title">Карта города</h3>
      <div className="geo-map-frame">
        <div ref={hostRef} className="geo-map-canvas" role="img" aria-label={map.title || "Карта города"} />
        <button type="button" className="geo-compass" aria-label="Показать всю карту" onClick={recenter}>
          <Icon name="plane" />
        </button>
        {!ready ? <div className="geo-map-pending">Открываем карту</div> : null}
      </div>
      {legend.length ? (
        <div className="geo-legend" role="list">
          {legend.map((item) => (
            <button
              key={item.name}
              type="button"
              className={`geo-legend-item ${selected?.layer === item.name ? "is-active" : ""}`}
              onClick={() => focusLayer(item.name)}
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

function itemWash(color: string): string {
  return `color-mix(in srgb, ${color} 16%, var(--card))`;
}
