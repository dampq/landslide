import { useEffect, useState } from "react";
import { TileLayer, useMap } from "react-leaflet";
import ReferenceMap from "./ReferenceMap";
export type BasemapStatus = {
  message: string;
  params?: Record<string, string | number>;
} | null;

/** Keep geographic context available without evading provider access policies. */
export default function Basemap({
  provider,
  onStatus,
}: {
  provider: string;
  onStatus: (status: BasemapStatus) => void;
}) {
  const map = useMap();
  const [available, setAvailable] = useState(false);
  const key = import.meta.env.VITE_CARTO_API_KEY || "";
  const carto = provider === "carto";
  const url = carto
    ? `https://a.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png?key=${encodeURIComponent(key)}`
    : "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
  const attribution =
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>' +
    (carto ? ' &copy; <a href="https://carto.com/attributions">CARTO</a>' : "");
  useEffect(() => {
    setAvailable(false);
    if (provider === "reference") {
      onStatus({
        message:
          "Offline geographic reference: public-domain boundaries, not a street map or live feed.",
      });
      return;
    }
    if (!["auto", "osm", "carto"].includes(provider)) {
      onStatus({
        message:
          "Unknown basemap provider. The regional reference map remains available.",
      });
      return;
    }
    if (carto && !key) {
      onStatus({
        message:
          "CARTO requires a browser API key configured by your administrator. The regional reference map remains available.",
      });
      return;
    }
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    let active = true;
    const z = map.getZoom(),
      point = map.project(map.getCenter(), z).divideBy(256).floor();
    const probe = url
      .replace("{z}", String(z))
      .replace("{x}", String(point.x))
      .replace("{y}", String(point.y));
    onStatus({
      message:
        "Checking online tiles; the regional reference map is available meanwhile.",
    });
    void fetch(probe, {
      signal: controller.signal,
      referrerPolicy: "strict-origin-when-cross-origin",
    })
      .then((response) => {
        if (!response.ok) {
          if (active)
            onStatus({
              message:
                "{provider} refused the background map request (HTTP {status}). The regional reference map and geographic markers remain available.",
              params: {
                provider: carto ? "CARTO" : "OpenStreetMap",
                status: response.status,
              },
            });
          return;
        }
        if (active) {
          setAvailable(true);
          onStatus(null);
        }
      })
      .catch(() => {
        if (active)
          onStatus({
            message:
              "Online tiles are unavailable. Using the regional reference map; try a normal browser tab or retry when connected.",
          });
      })
      .finally(() => clearTimeout(timeout));
    return () => {
      active = false;
      controller.abort();
      clearTimeout(timeout);
    };
  }, [map, provider, key, carto, url, onStatus]);
  return available ? (
    <TileLayer
      url={url}
      attribution={attribution}
      maxZoom={carto ? 20 : 19}
      referrerPolicy="strict-origin-when-cross-origin"
      eventHandlers={{
        tileerror: () => {
          setAvailable(false);
          onStatus({
            message:
              "Some online tiles failed to load. The regional reference map and geographic markers remain available.",
          });
        },
      }}
    />
  ) : (
    <ReferenceMap />
  );
}
