import { useEffect, useState } from "react";
import { GeoJSON, Pane, Marker } from "react-leaflet";
import { divIcon } from "leaflet";
import type { FeatureCollection } from "geojson";
import { useApp } from "../App";
const escape = (value: string) =>
  value.replace(
    /[&<>"']/g,
    (character) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        character
      ]!,
  );
/** Public-domain geographic context, independently bundled; never cached tiles. */
export default function ReferenceMap() {
  const { t } = useApp();
  const [data, setData] = useState<FeatureCollection | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    void fetch("/reference-map.geojson", { signal: controller.signal })
      .then((r) => {
        if (!r.ok) throw new Error("Reference map unavailable");
        return r.json();
      })
      .then(setData)
      .catch(() => {});
    return () => controller.abort();
  }, []);
  if (!data) return null;
  return (
    <>
      <Pane name="reference-map" style={{ zIndex: 190 }}>
        <GeoJSON
          data={data}
          interactive={false}
          attribution='<a href="https://www.naturalearthdata.com/">Natural Earth</a> (public domain)'
          style={(f) => ({
            className:
              f?.properties?.level === "state"
                ? "reference-state"
                : "reference-country",
            color: f?.properties?.level === "state" ? "#64748b" : "#94a3b8",
            weight: f?.properties?.level === "state" ? 1.3 : 0.8,
            fillColor: f?.properties?.level === "state" ? "#dce9cf" : "#f0eee4",
            fillOpacity: 1,
          })}
        />
      </Pane>
      <Pane
        name="reference-labels"
        style={{ zIndex: 350, pointerEvents: "none" }}
      >
        {data.features
          .filter((f) => f.properties?.level === "state")
          .map((f) => (
            <Marker
              key={f.properties!.name}
              position={[f.properties!.labelLat, f.properties!.labelLng]}
              interactive={false}
              keyboard={false}
              icon={divIcon({
                className: "reference-map-label",
                html: escape(t(f.properties!.name)),
                iconSize: [120, 22],
                iconAnchor: [60, 11],
              })}
            />
          ))}
      </Pane>
    </>
  );
}
