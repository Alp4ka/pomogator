import { useEffect, useMemo, useRef, useState } from "react";

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
const GOOGLE_MAPS_API_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY?.trim() ?? "";

let googleMapsPromise: Promise<typeof google> | null = null;

function googleGlobal(): typeof google | undefined {
  return (globalThis as typeof globalThis & { google?: typeof google }).google;
}

function loadGoogleMaps(apiKey: string): Promise<typeof google> {
  const loaded = googleGlobal();
  if (loaded?.maps) return Promise.resolve(loaded);
  if (googleMapsPromise) return googleMapsPromise;

  googleMapsPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    const params = new URLSearchParams({ key: apiKey, v: "weekly", language: "ru", region: "BR" });
    script.src = `https://maps.googleapis.com/maps/api/js?${params.toString()}`;
    script.async = true;
    script.defer = true;
    script.onload = () => {
      const maps = googleGlobal();
      if (maps?.maps) resolve(maps);
      else reject(new Error("Google Maps API did not initialize"));
    };
    script.onerror = () => reject(new Error("Google Maps API failed to load"));
    document.head.append(script);
  });
  return googleMapsPromise;
}

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

function googleDirectionsUrl(place: GeoPlace): string {
  return `https://www.google.com/maps/dir/?api=1&destination=${place.lat.toFixed(6)},${place.lng.toFixed(6)}`;
}

function googleMyMapsUrl(mapId: string): string {
  return `https://www.google.com/maps/d/viewer?mid=${encodeURIComponent(mapId)}`;
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
    return source.filter(Boolean).map((name) => ({
      name,
      count: places.filter((place) => place.layer === name).length,
      ...layerLook(name),
    }));
  }, [map.layers, places]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activeLayer, setActiveLayer] = useState<string | null>(() => legend[0]?.name ?? null);
  const [mapStatus, setMapStatus] = useState<"loading" | "ready" | "error" | "unconfigured">(
    GOOGLE_MAPS_API_KEY ? "loading" : "unconfigured",
  );
  const mapHostRef = useRef<HTMLDivElement | null>(null);
  const googleMapRef = useRef<google.maps.Map | null>(null);
  const visiblePlaces = activeLayer
    ? places.filter((place) => place.layer === activeLayer)
    : places;
  const externalMapUrl = map.source_url || googleMyMapsUrl(map.map_id);

  useEffect(() => {
    const host = mapHostRef.current;
    if (!host || !GOOGLE_MAPS_API_KEY || !places.length) return;

    let disposed = false;
    let tilesListener: google.maps.MapsEventListener | null = null;
    let watchdog: number | null = null;
    const markers: google.maps.Marker[] = [];

    void loadGoogleMaps(GOOGLE_MAPS_API_KEY)
      .then((maps) => {
        if (disposed) return;
        const bounds = new maps.maps.LatLngBounds();
        const instance = new maps.maps.Map(host, {
          center: { lat: places[0]!.lat, lng: places[0]!.lng },
          zoom: 12,
          disableDefaultUI: true,
          zoomControl: true,
          fullscreenControl: true,
          clickableIcons: false,
          gestureHandling: "cooperative",
          mapTypeControl: false,
          streetViewControl: false,
        });
        googleMapRef.current = instance;

        for (const place of places) {
          const look = layerLook(place.layer);
          const marker = new maps.maps.Marker({
            map: instance,
            position: { lat: place.lat, lng: place.lng },
            title: place.name,
            icon: {
              path: maps.maps.SymbolPath.CIRCLE,
              scale: 8,
              fillColor: place.color || look.color,
              fillOpacity: 1,
              strokeColor: "#ffffff",
              strokeOpacity: 1,
              strokeWeight: 2,
            },
          });
          marker.addListener("click", () => {
            setSelectedId(place.id);
            setActiveLayer(place.layer);
          });
          markers.push(marker);
          bounds.extend(marker.getPosition()!);
        }

        instance.fitBounds(bounds, 34);
        tilesListener = maps.maps.event.addListenerOnce(instance, "tilesloaded", () => {
          if (!disposed) setMapStatus("ready");
        });
        watchdog = window.setTimeout(() => {
          if (!disposed) setMapStatus("ready");
        }, 8000);
      })
      .catch(() => {
        if (!disposed) setMapStatus("error");
      });

    return () => {
      disposed = true;
      if (watchdog !== null) window.clearTimeout(watchdog);
      tilesListener?.remove();
      for (const marker of markers) marker.setMap(null);
      googleMapRef.current = null;
    };
  }, [places]);

  function focusPlace(place: GeoPlace) {
    setSelectedId(place.id);
    setActiveLayer(place.layer);
    googleMapRef.current?.panTo({ lat: place.lat, lng: place.lng });
    googleMapRef.current?.setZoom(15);
  }

  function focusLayer(layer: string) {
    setActiveLayer(layer);
    const matches = places.filter((place) => place.layer === layer);
    if (!matches.length) return;
    setSelectedId(matches[0]!.id);
    const maps = googleGlobal();
    const instance = googleMapRef.current;
    if (!maps || !instance) return;
    const bounds = new maps.maps.LatLngBounds();
    for (const place of matches) bounds.extend({ lat: place.lat, lng: place.lng });
    if (matches.length === 1) {
      instance.panTo({ lat: matches[0]!.lat, lng: matches[0]!.lng });
      instance.setZoom(15);
    } else {
      instance.fitBounds(bounds, 42);
    }
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
      {GOOGLE_MAPS_API_KEY && places.length ? (
        <div className="geo-map-frame">
          <div ref={mapHostRef} className="geo-map-canvas" aria-label={map.title || "Карта города"} />
          {mapStatus === "loading" ? <div className="geo-map-pending">Загружаем карту и точки…</div> : null}
          {mapStatus === "error" ? (
            <div className="geo-map-fallback">
              <span>Google Maps не загрузилась</span>
              <a href={externalMapUrl} target="_blank" rel="noreferrer">Открыть карту</a>
            </div>
          ) : null}
        </div>
      ) : (
        <a className="geo-map-unconfigured" href={externalMapUrl} target="_blank" rel="noreferrer">
          <strong>Открыть карту в Google Maps</strong>
          <span>Карта откроется в отдельном окне</span>
        </a>
      )}
      {legend.length ? (
        <div className="geo-legend" role="list">
          {legend.map((item) => (
            <button
              key={item.name}
              type="button"
              className={`geo-legend-item ${activeLayer === item.name ? "is-active" : ""}`}
              onClick={() => focusLayer(item.name)}
            >
              <span className="geo-legend-icon" style={{ color: item.color }}>
                <Icon name={item.icon} />
              </span>
              <span>{item.short}</span>
              <small>{item.count}</small>
            </button>
          ))}
        </div>
      ) : null}
      {visiblePlaces.length ? (
        <div className="geo-place-list">
          {visiblePlaces.map((place) => {
            const look = layerLook(place.layer);
            return (
              <article key={place.id} className={`geo-place-row ${selectedId === place.id ? "is-active" : ""}`}>
                <button type="button" className="geo-place-main" onClick={() => focusPlace(place)}>
                  <span className="geo-spot-badge" style={{ background: itemWash(look.color), color: look.color }}>
                    <Icon name={look.icon} />
                  </span>
                  <span className="geo-spot-copy">
                    <strong>{place.name}</strong>
                    <em>Показать на карте</em>
                  </span>
                </button>
                <a
                  className="geo-spot-route"
                  href={googleDirectionsUrl(place)}
                  target="_blank"
                  rel="noreferrer"
                  aria-label={`Построить маршрут: ${place.name}`}
                >
                  <Icon name="plane" />
                </a>
              </article>
            );
          })}
        </div>
      ) : null}
    </section>
  );
}
