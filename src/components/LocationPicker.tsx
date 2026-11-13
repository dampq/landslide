import { useCallback, useEffect, useMemo, useState } from "react";
import {
  MapContainer,
  CircleMarker,
  Popup,
  useMap,
  useMapEvents,
} from "react-leaflet";
import { useApp } from "../App";
import { Button } from "./ui";
import Basemap, { type BasemapStatus } from "./Basemap";

type Point = { lat: string | number; lng: string | number };
type SavedLocation = { id: string; name?: string; lat?: number; lng?: number };
function valid(p: Point) {
  return (
    String(p.lat).trim() !== "" &&
    String(p.lng).trim() !== "" &&
    Number.isFinite(Number(p.lat)) &&
    Number.isFinite(Number(p.lng)) &&
    Math.abs(Number(p.lat)) <= 90 &&
    Math.abs(Number(p.lng)) <= 180
  );
}
function ClickPoint({
  onPick,
}: {
  onPick: (lat: number, lng: number) => void;
}) {
  useMapEvents({
    click(e) {
      onPick(e.latlng.lat, e.latlng.wrap().lng);
    },
  });
  return null;
}
function FitLocations({ locations }: { locations: SavedLocation[] }) {
  const map = useMap();
  useEffect(() => {
    if (locations.length)
      map.fitBounds(
        locations.map((v) => [v.lat!, v.lng!] as [number, number]),
        { padding: [24, 24], maxZoom: 12 },
      );
  }, [map, locations]);
  return null;
}
export default function LocationPicker({
  value,
  onChange,
  disabled = false,
  locations,
  selectedId = "",
  onSelectLocation,
}: {
  value?: Point;
  onChange?: (lat: string, lng: string) => void;
  disabled?: boolean;
  locations?: SavedLocation[];
  selectedId?: string;
  onSelectLocation?: (id: string) => void;
}) {
  const { t } = useApp();
  const [open, setOpen] = useState(false),
    [draft, setDraft] = useState<Point | null>(null),
    [draftId, setDraftId] = useState("");
  const [status, setStatus] = useState<BasemapStatus>(null);
  const mapStatus = useCallback((s: BasemapStatus) => setStatus(s), []);
  const savedMode = locations !== undefined;
  const candidates = useMemo(
    () =>
      (locations || []).filter((v) =>
        valid({ lat: v.lat ?? "", lng: v.lng ?? "" }),
      ),
    [locations],
  );
  function show() {
    const selected = candidates.find((v) => v.id === selectedId);
    setDraft(
      savedMode && selected
        ? { lat: selected.lat!, lng: selected.lng! }
        : value && valid(value)
          ? value
          : null,
    );
    setDraftId(selected?.id || "");
    setOpen(true);
  }
  const center: [number, number] =
    draft && valid(draft)
      ? [Number(draft.lat), Number(draft.lng)]
      : [25.9, 92.5];
  const canUse =
    !disabled &&
    !!draft &&
    valid(draft) &&
    (!savedMode || candidates.some((v) => v.id === draftId));
  return (
    <div className="my-2 min-w-0 space-y-2">
      <Button
        type="button"
        disabled={disabled || (savedMode && !candidates.length)}
        variant="outline"
        onClick={show}
      >
        {t(
          savedMode
            ? "Select saved location on map"
            : "Select coordinates on map",
        )}
      </Button>
      {savedMode && !candidates.length && (
        <p className="text-sm">{t("No saved locations to select on map")}</p>
      )}
      {open && (
        <div
          className="space-y-2 rounded-xl border p-3"
          role="group"
          aria-label={t(
            savedMode ? "Saved location map picker" : "Coordinate map picker",
          )}
        >
          <p className="text-sm">
            {t(
              savedMode
                ? "Saved location map guidance"
                : "Coordinate map guidance",
            )}
          </p>
          <div style={{ height: 280 }}>
            <MapContainer
              center={center}
              zoom={draft ? 11 : 6}
              scrollWheelZoom={false}
              style={{ height: "100%", width: "100%" }}
            >
              <Basemap provider="auto" onStatus={mapStatus} />
              {!savedMode && (
                <ClickPoint
                  onPick={(lat, lng) => {
                    if (!disabled)
                      setDraft({ lat: lat.toFixed(6), lng: lng.toFixed(6) });
                  }}
                />
              )}
              {savedMode && <FitLocations locations={candidates} />}
              {savedMode
                ? candidates.map((v) => (
                    <CircleMarker
                      key={v.id}
                      center={[v.lat!, v.lng!]}
                      radius={draftId === v.id ? 10 : 7}
                      pathOptions={{
                        color: draftId === v.id ? "#c2410c" : "#1d4ed8",
                      }}
                      eventHandlers={{
                        click: () => {
                          if (!disabled) {
                            setDraftId(v.id);
                            setDraft({ lat: v.lat!, lng: v.lng! });
                          }
                        },
                      }}
                    >
                      <Popup>{v.name || v.id}</Popup>
                    </CircleMarker>
                  ))
                : draft && (
                    <CircleMarker
                      center={[Number(draft.lat), Number(draft.lng)]}
                      radius={8}
                    >
                      <Popup>{t("Selected map position")}</Popup>
                    </CircleMarker>
                  )}
            </MapContainer>
          </div>
          {status && (
            <p className="text-xs">{t(status.message, status.params)}</p>
          )}
          {draft && (
            <p role="status">
              {t("Selected map position")}: {Number(draft.lat).toFixed(6)},{" "}
              {Number(draft.lng).toFixed(6)}
              {savedMode &&
                ` · ${candidates.find((v) => v.id === draftId)?.name || draftId}`}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              disabled={!canUse}
              onClick={() => {
                if (!draft || !canUse) return;
                if (savedMode) onSelectLocation?.(draftId);
                else onChange?.(String(draft.lat), String(draft.lng));
                setOpen(false);
              }}
            >
              {t(
                savedMode
                  ? "Use selected saved location"
                  : "Use selected coordinates",
              )}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
            >
              {t("Cancel map selection")}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
