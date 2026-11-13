import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { MapContainer, CircleMarker, Popup, useMapEvents } from "react-leaflet";
import { useApp } from "../App";
import { post } from "../lib";
import { Card, Input, Button } from "./ui";
import Basemap from "./Basemap";

export function AssessmentPicker({
  onPick,
}: {
  onPick: (lat: number, lng: number) => void;
}) {
  useMapEvents({
    click(e) {
      onPick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

export default function CoordinateAssessment({ version }: { version: string }) {
  const { t } = useApp();
  const [params] = useSearchParams();
  const [lat, setLat] = useState(params.get("lat") || ""),
    [lng, setLng] = useState(params.get("lng") || "");
  const [preview, setPreview] = useState<any>(null),
    [result, setResult] = useState<any>(null);
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [mapStatus, setMapStatus] = useState<any>(null);
  const mapCallback = useCallback((s: any) => setMapStatus(s), []);
  useEffect(() => {
    setPreview(null);
    setResult(null);
    setError("");
  }, [version]);
  const valid =
    lat.trim() !== "" &&
    lng.trim() !== "" &&
    Number.isFinite(Number(lat)) &&
    Number.isFinite(Number(lng)) &&
    Math.abs(Number(lat)) <= 90 &&
    Math.abs(Number(lng)) <= 180;
  function change(a: string, b: string) {
    setLat(a);
    setLng(b);
    setPreview(null);
    setResult(null);
    setError("");
  }
  async function act(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await fn();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const current =
    preview?.modelVersion === version &&
    preview?.lat === Number(lat) &&
    preview?.lng === Number(lng);
  return (
    <Card className="my-5 space-y-3 p-5">
      <h2 className="text-xl font-bold">{t("Location-based assessment")}</h2>
      <p>{t("Coordinate assessment guidance")}</p>
      <div className="grid gap-3 md:grid-cols-2">
        <label>
          {t("Assessment latitude")}
          <Input
            aria-label={t("Assessment latitude")}
            type="number"
            step="any"
            min={-90}
            max={90}
            value={lat}
            disabled={busy}
            onChange={(e) => change(e.target.value, lng)}
          />
        </label>
        <label>
          {t("Assessment longitude")}
          <Input
            aria-label={t("Assessment longitude")}
            type="number"
            step="any"
            min={-180}
            max={180}
            value={lng}
            disabled={busy}
            onChange={(e) => change(lat, e.target.value)}
          />
        </label>
      </div>
      <details>
        <summary>{t("Select assessment coordinates on map")}</summary>
        <div style={{ height: 280 }}>
          <MapContainer
            center={valid ? [Number(lat), Number(lng)] : [25.9, 92.5]}
            zoom={6}
            scrollWheelZoom={false}
            style={{ height: "100%" }}
          >
            <Basemap provider="auto" onStatus={mapCallback} />
            <AssessmentPicker
              onPick={(a, b) => {
                if (!busy) change(a.toFixed(6), b.toFixed(6));
              }}
            />
            {valid && (
              <CircleMarker center={[Number(lat), Number(lng)]} radius={7}>
                <Popup>{t("Assessment coordinates")}</Popup>
              </CircleMarker>
            )}
          </MapContainer>
        </div>
        {mapStatus && <p>{t(mapStatus.message, mapStatus.params)}</p>}
      </details>
      <Button
        disabled={busy || !valid}
        onClick={() =>
          act(async () => {
            setPreview(null);
            setResult(null);
            setPreview(
              await post("/api/assessment/features", {
                lat: Number(lat),
                lng: Number(lng),
                modelVersion: version,
              }),
            );
          })
        }
      >
        {t("Extract environmental inputs")}
      </Button>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      {busy && <p role="status">{t("Loading…")}</p>}
      {current && (
        <>
          <p>
            {t("Extraction ID")}: {preview.id}
          </p>
          <p>
            {t("State")}: {preview.state}
          </p>
          <p>{t("Extracted input review notice")}</p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr>
                  {["Feature", "Value", "Unit", "Source status", "Source"].map(
                    (k) => (
                      <th scope="col" className="p-2 text-left" key={k}>
                        {t(k)}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {preview.features.map((f: any) => {
                  const p =
                    preview.provenance.find((p: any) => p.name === f.name) ||
                    {};
                  return (
                    <tr key={f.name}>
                      <th scope="row" className="break-words p-2 text-left">
                        {f.name}
                      </th>
                      <td className="p-2">
                        {preview.inputs[f.name] ?? t("Unavailable")}
                      </td>
                      <td className="p-2">{f.unit}</td>
                      <td className="p-2">{p.status}</td>
                      <td className="p-2">
                        <details>
                          <summary>
                            {p.dataset_name || t("Unavailable")}
                          </summary>
                          <p>
                            {p.product_version} ·{" "}
                            {p.temporal_coverage || t("Not provided")}
                          </p>
                          <p>
                            {p.crs} · {p.resolution?.join(" × ")}
                          </p>
                          <p>{p.file}</p>
                          <p>
                            {t("Source checksum")}:{" "}
                            {p.sha256 || t("Not provided")}
                          </p>
                          <p>
                            {t("Raw source value")}:{" "}
                            {p.rawValue ?? t("Unavailable")} · {t("Scale")}:{" "}
                            {p.scale ?? 1}
                          </p>
                          <p>{t(p.evidenceType || "Not provided")}</p>
                          <p>
                            {t("Grid resolution (CRS units)")}:{" "}
                            {p.resolution?.join(" × ")}
                          </p>
                          <p>{p.depth_interval}</p>
                          <p>{p.attribution}</p>
                          <p>{p.licence}</p>
                          {p.official_source_url && (
                            <a
                              className="underline"
                              href={p.official_source_url}
                              target="_blank"
                              rel="noreferrer"
                            >
                              {t("Source")}
                            </a>
                          )}
                        </details>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p>
            {t("Missing fields")}: {preview.missingFields.join(", ") || "—"}
          </p>
          <p>{t("Model imputation guidance")}</p>
          <p>{t("Training unit convention notice")}</p>
          {!preview.canScore && (
            <p role="note">{t("Incomplete environmental assessment")}</p>
          )}
          <Button
            disabled={busy || !preview.canScore || !!result}
            onClick={() =>
              act(async () => {
                setResult(
                  await post("/api/assessment/run", {
                    extractionId: preview.id,
                  }),
                );
              })
            }
          >
            {t("Run inspected assessment")}
          </Button>
        </>
      )}
      {result && (
        <div role="status" className="success">
          <b>
            {t("Relative score")}:{" "}
            {result.experimental_presence_background_score.toFixed(8)}
          </b>
          <p>
            {t("Model version")}: {result.modelVersion}
          </p>
          <p>{t("Experimental score notice")}</p>
          <p>
            {t("Imputed fields")}: {result.imputed_fields.join(", ") || "—"}
          </p>
          {version === "2" && <p>{t("V2 comparison notice")}</p>}
        </div>
      )}
    </Card>
  );
}
