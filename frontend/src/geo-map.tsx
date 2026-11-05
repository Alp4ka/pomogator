import { useEffect, useMemo, useRef, useState } from "react";

import { Icon } from "./icons";
import "leaflet/dist/leaflet.css";

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

const FALLBACK_COLORS = ["#1b8f6a", "#0288d1", "#e65100", "#9c27b0", "#c48912", "#880e4f"];

function layerColor(name: string, layers: GeoLayer[], placeColor?: string): string {
  if (placeColor) return placeColor;
  const match = layers.find((layer) => layer.name === name);
  if (match?.color) return match.color;
  const index = Math.max(0, layers.findIndex((layer) => layer.name === name));
  return FALLBACK_COLORS[index % FALLBACK_COLORS.length] ?? FALLBACK_COLORS[0];
}

function googlePlaceUrl(place: GeoPlace): string {
  return `https://www.google.com/maps/search/?api=1&query=${place.lat.toFixed(6)},${place.lng.toFixed(6)}`;
}

function googleDirectionsUrl(place: GeoPlace): string {
  return `https://www.google.com/maps/dir/?api=1&destination=${place.lat.toFixed(6)},${place.lng.toFixed(6)}`;
}

function groupedPlaces(places: GeoPlace[]): [string, GeoPlace[]][] {
  const order: string[] = [];
  const buckets = new Map<string, GeoPlace[]>();
  for (const place of places) {
    const key = place.layer || "Места";
    if (!buckets.has(key)) {
      order.push(key);
      buckets.set(key, []);
    }
    buckets.get(key)!.push(place);
  }
  return order.map((name) => [name, buckets.get(name) ?? []]);
}

function readTheme(): "light" | "dark" {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

export function GeoMapCard({ map }: { map: GeoMapBlock }) {
  const places = useMemo(
    () => (map.places ?? []).filter((place) => Number.isFinite(place.lat) && Number.isFinite(place.lng)),
    [map.places],
  );
  const layers = useMemo(() => map.layers ?? [], [map.layers]);
  const groups = useMemo(() => groupedPlaces(places), [places]);
  const hostRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<import("leaflet").Map | null>(null);
  const [selected, setSelected] = useState<GeoPlace | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const host = hostRef.current;
    if (!host || !places.length) return;
    let cancelled = false;
    let observer: ResizeObserver | undefined;

    void import("leaflet").then((leaflet) => {
      if (cancelled || !hostRef.current) return;
      const L = leaflet.default ?? leaflet;
      host.dataset.theme = readTheme();
      const map = L.map(host, {
        zoomControl: false,
        attributionControl: true,
        scrollWheelZoom: false,
      });
      L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
        subdomains: "abc",
        maxZoom: 19,
      }).addTo(map);
      L.control.zoom({ position: "bottomright" }).addTo(map);
      const bounds = L.latLngBounds([]);
      for (const place of places) {
        const color = layerColor(place.layer, layers, place.color);
        const marker = L.marker([place.lat, place.lng], {
          icon: L.divIcon({
            className: "geo-pin",
            html: `<span class="geo-pin-dot" style="background:${color}"></span>`,
            iconSize: [22, 28],
            iconAnchor: [11, 26],
          }),
          title: place.name,
        }).addTo(map);
        marker.on("click", () => setSelected(place));
        bounds.extend([place.lat, place.lng]);
      }
      if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [28, 28], maxZoom: 14 });
      }
      observer = new ResizeObserver(() => map.invalidateSize());
      observer.observe(host);
      mapRef.current = map;
      setReady(true);
    });

    return () => {
      cancelled = true;
      observer?.disconnect();
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, [layers, places]);

  function focusPlace(place: GeoPlace) {
    setSelected(place);
    const map = mapRef.current;
    if (map) map.flyTo([place.lat, place.lng], Math.max(map.getZoom(), 15), { duration: 0.4 });
  }

  if (!places.length) {
    return (
      <section className="geo-card">
        <div className="geo-card-head">
          <span className="geo-card-kicker">Карта</span>
          <h3>{map.title || "Места на карте"}</h3>
        </div>
        <p className="geo-card-empty">Нажмите «Обновить», чтобы загрузить точки с Google Maps.</p>
      </section>
    );
  }

  return (
    <section className="geo-card">
      <div className="geo-map-frame">
        <div ref={hostRef} className="geo-map-canvas" role="img" aria-label={map.title || "Карта"} />
        {!ready ? <div className="geo-map-pending">Открываем карту</div> : null}
      </div>
      <div className="geo-place-list">
        {groups.map(([layer, items]) => (
          <div key={layer} className="geo-place-group">
            <p className="geo-place-layer">
              <span className="geo-place-dot" style={{ background: layerColor(layer, layers) }} />
              {layer}
              <span className="geo-place-count">{items.length}</span>
            </p>
            {items.map((place) => (
              <button
                key={place.id}
                type="button"
                className={`geo-place-row ${selected?.id === place.id ? "is-active" : ""}`}
                onClick={() => focusPlace(place)}
              >
                <span>{place.name}</span>
                <Icon name="pin" />
              </button>
            ))}
          </div>
        ))}
      </div>
      {selected ? (
        <div className="geo-layer" role="dialog" aria-modal="true" aria-label={selected.name}>
          <button type="button" className="geo-backdrop" aria-label="Закрыть" onClick={() => setSelected(null)} />
          <div className="geo-sheet">
            <div className="geo-sheet-head">
              <div>
                <p className="geo-sheet-layer">{selected.layer}</p>
                <h2>{selected.name}</h2>
              </div>
              <button type="button" className="toc-sheet-close" onClick={() => setSelected(null)}>
                Закрыть
              </button>
            </div>
            <div className="geo-sheet-actions">
              <a className="btn" href={googlePlaceUrl(selected)} target="_blank" rel="noreferrer">
                Открыть в Google Maps
              </a>
              <a className="btn btn-secondary" href={googleDirectionsUrl(selected)} target="_blank" rel="noreferrer">
                Маршрут
              </a>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}
