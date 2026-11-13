import { useState } from "react";
import { useApp } from "../App";
import { post } from "../lib";
import { Button } from "./ui";

export type LocationDetails = {
  lat: number;
  lng: number;
  fields: Record<string, string | number>;
  provenance: Record<string, any>;
  unavailable: Record<string, string>;
};
const labels: Record<string, string> = {
  name: "Name",
  district: "District",
  state: "State",
  slope: "Slope (degrees)",
};

export default function LocationDetailsLookup({
  lat,
  lng,
  onApply,
}: {
  lat: string;
  lng: string;
  onApply: (result: LocationDetails, replace: boolean) => void;
}) {
  const { t } = useApp();
  const [result, setResult] = useState<LocationDetails | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [replace, setReplace] = useState(false);
  const valid =
    lat.trim() !== "" &&
    lng.trim() !== "" &&
    Number.isFinite(Number(lat)) &&
    Number.isFinite(Number(lng)) &&
    Math.abs(Number(lat)) <= 90 &&
    Math.abs(Number(lng)) <= 180;
  async function lookup() {
    setBusy(true);
    setError("");
    setResult(null);
    try {
      setResult(
        await post("/api/location/details", {
          lat: Number(lat),
          lng: Number(lng),
        }),
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="space-y-3 rounded-xl border p-4">
      <p className="text-sm">
        {t(
          "Look up place details using these coordinates. This sends the coordinates to OpenStreetMap Nominatim. Terrain lookup uses local prepared data.",
        )}
      </p>
      <Button
        type="button"
        variant="outline"
        disabled={!valid || busy}
        onClick={lookup}
      >
        {t(busy ? "Loading…" : "Look up location details")}
      </Button>
      {error && <p role="alert">{error}</p>}
      {result && (
        <>
          <p>
            {t(
              "Review suggestions against the map. Nearby mapped addresses may be approximate. Severity is not inferred.",
            )}
          </p>
          <dl className="space-y-2">
            {Object.entries(labels).map(([key, label]) => (
              <div key={key}>
                <dt className="font-bold">{t(label)}</dt>
                <dd>{result.fields[key] ?? t("Unavailable")}</dd>
                <dd className="text-sm text-slate-600">
                  {result.provenance[key]?.source || result.unavailable[key]}
                </dd>
                {result.provenance[key] && (
                  <details>
                    <summary>{t("Source details")}</summary>
                    <pre className="overflow-auto text-xs">
                      {JSON.stringify(result.provenance[key], null, 2)}
                    </pre>
                  </details>
                )}
              </div>
            ))}
          </dl>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={replace}
              onChange={(e) => setReplace(e.target.checked)}
            />
            {t("Replace existing values with available suggestions")}
          </label>
          <Button
            type="button"
            disabled={!Object.keys(result.fields).length}
            onClick={() => onApply(result, replace)}
          >
            {t("Apply location suggestions")}
          </Button>
          <p className="text-sm">
            {t(
              "Empty fields are filled by default. Unavailable values stay unchanged. Review and save the form when ready.",
            )}
          </p>
        </>
      )}
    </div>
  );
}
