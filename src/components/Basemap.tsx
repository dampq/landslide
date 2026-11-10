import { useEffect, useState } from "react";
import { TileLayer, useMap } from "react-leaflet";

/** Display-only tiles: never proxied, bulk-downloaded or cached by our worker. */
export default function Basemap({
  onStatus,
}: {
  onStatus: (message: string) => void;
}) {
  const map = useMap();
  const [available, setAvailable] = useState(false);
  const provider = import.meta.env.VITE_MAP_PROVIDER || "osm";
  const cartoKey = import.meta.env.VITE_CARTO_API_KEY || "";
  const carto = provider === "carto";
  const template = carto
    ? `https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=${encodeURIComponent(cartoKey)}`
    : "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
  const attribution =
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>' +
    (carto ? ' &copy; <a href="https://carto.com/attributions">CARTO</a>' : "");

  useEffect(() => {
    setAvailable(false);
    if (!["osm", "carto"].includes(provider)) {
      onStatus("Unknown basemap provider. Configure osm or carto.");
      return;
    }
    if (carto && !cartoKey) {
      onStatus(
        "CARTO requires an API key. Configure the free-tier key in VITE_CARTO_API_KEY. Geographic records remain available.",
      );
      return;
    }
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    let active = true;
    // Test one visible tile before rendering the layer. Some providers return a
    // decodable error image with HTTP 403, which Leaflet can otherwise display.
    const z = map.getZoom();
    const point = map.project(map.getCenter(), z).divideBy(256).floor();
    const url = template
      .replace("{z}", String(z))
      .replace("{x}", String(point.x))
      .replace("{y}", String(point.y));
    onStatus("Checking background map access…");
    void fetch(url, {
      signal: controller.signal,
      referrerPolicy: "strict-origin-when-cross-origin",
    })
      .then((response) => {
        if (!response.ok) {
          if (response.status === 401 || response.status === 403)
            throw new Error(
              `${carto ? "CARTO" : "OpenStreetMap"} refused the background map request (HTTP ${response.status}). Open the website in a normal browser tab; if access remains blocked, use an authorised basemap provider. Location markers and stored data are still available.`,
            );
          throw new Error(
            "Background map tiles are currently unavailable. Location markers and stored data are still available.",
          );
        }
        if (active) {
          setAvailable(true);
          onStatus("");
        }
      })
      .catch((error) => {
        if (active)
          onStatus(
            error.name === "AbortError"
              ? "Background map request timed out. Check your network connection; stored markers remain available."
              : error.message === "Failed to fetch"
                ? "Cannot reach the background map provider. Check network access and open the website in a normal browser tab. Stored markers remain available."
                : error.message,
          );
      })
      .finally(() => clearTimeout(timeout));
    return () => {
      active = false;
      controller.abort();
      clearTimeout(timeout);
    };
  }, [map, provider, carto, cartoKey, template, onStatus]);

  return available ? (
    <TileLayer
      url={template}
      attribution={attribution}
      maxZoom={carto ? 20 : 19}
      referrerPolicy="strict-origin-when-cross-origin"
      eventHandlers={{
        tileerror: () =>
          onStatus(
            "Some background map tiles failed to load. Check provider access or connection; geographic markers remain available.",
          ),
      }}
    />
  ) : null;
}
