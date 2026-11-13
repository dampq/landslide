import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useApp } from "../App";
import { useData, post, patch, time } from "../lib";
import { Card, Button, Input, Select } from "./ui";
import LocationPicker from "./LocationPicker";

export default function IncidentResponse({ reportId }: { reportId: string }) {
  const { t } = useApp();
  const report = useData(
    `/api/response/reports/${encodeURIComponent(reportId)}`,
  );
  const teams = useData("/api/records/teams?limit=500");
  const media = useData(`/api/reports/${encodeURIComponent(reportId)}/media`);
  const [lat, setLat] = useState(""),
    [lng, setLng] = useState(""),
    [team, setTeam] = useState("");
  const [note, setNote] = useState(""),
    [correction, setCorrection] = useState(""),
    [urgentReason, setUrgentReason] = useState("");
  const [showTeamSetup, setShowTeamSetup] = useState(false);
  const [practiceTeam, setPracticeTeam] = useState(false);
  const [mode, setMode] = useState("verify-and-assign");
  const [destinationConfirmed, setDestinationConfirmed] = useState(false),
    [teamConfirmed, setTeamConfirmed] = useState(false);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    if (report.data?.id) {
      setLat(String(report.data.lat));
      setLng(String(report.data.lng));
    }
  }, [report.data?.id]);
  const refresh = async () => {
    await Promise.all([report.refresh(), teams.refresh()]);
  };
  async function action(fn: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError((e as Error).message);
      await refresh();
    } finally {
      setBusy(false);
    }
  }
  const r = report.data;
  const all = teams.data?.items || [];
  const available = all.filter((v: any) => v.status === "Available");
  const valid =
    lat.trim() !== "" &&
    lng.trim() !== "" &&
    Number.isFinite(Number(lat)) &&
    Number.isFinite(Number(lng)) &&
    Math.abs(Number(lat)) <= 90 &&
    Math.abs(Number(lng)) <= 180;
  const eligible = available.filter(
    (v: any) =>
      [v.coverageWest, v.coverageSouth, v.coverageEast, v.coverageNorth].some(
        (x) => x == null || x === "",
      ) ||
      (Number(lng) >= v.coverageWest &&
        Number(lng) <= v.coverageEast &&
        Number(lat) >= v.coverageSouth &&
        Number(lat) <= v.coverageNorth),
  );
  const corrected = r && (Number(lat) !== r.lat || Number(lng) !== r.lng);
  const active = r?.deployments?.some((d: any) =>
    ["Assigned", "En Route", "On Site"].includes(d.status),
  );
  const verified = r?.status === "Verified";
  const closed = r && ["Rejected", "Resolved"].includes(r.status);
  const setDestination = (a: string, b: string) => {
    setLat(a);
    setLng(b);
    setDestinationConfirmed(false);
    setTeamConfirmed(false);
  };
  async function createTeam(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    await action(async () => {
      const saved = await post("/api/records/teams", {
        name: values.name,
        source: values.source,
        simulated: practiceTeam,
      });
      setTeam(saved.id);
      setTeamConfirmed(false);
      setShowTeamSetup(false);
      setPracticeTeam(false);
    });
  }
  return (
    <>
      <h1 className="mb-3 text-3xl font-bold">{t("Incident response")}</h1>
      <p>{t("Dispatch separation notice")}</p>
      {(report.error || teams.error || media.error || error) && (
        <p role="alert" className="error my-3">
          {report.error || teams.error || media.error || error}
        </p>
      )}
      {r && (
        <Card className="my-4 space-y-3 p-5">
          <p>
            {t("Report ID")}: {r.id}
          </p>
          <p>
            {t(r.status)} · {r.location}
          </p>
          <p>{r.description}</p>
          <p>
            {t("Reported GPS")}: {r.lat}, {r.lng} · {t("GPS accuracy (metres)")}
            : {r.gpsAccuracyM ?? t("Not provided")}
          </p>
          <div className="flex flex-wrap gap-3">
            {media.data?.items.map((m: any) => (
              <a
                className="text-blue-700 underline"
                href={`/api/media/${m.id}`}
                key={m.id}
              >
                {m.filename}
                {m.mime?.startsWith("image/") && (
                  <img
                    className="max-h-48 max-w-full"
                    src={`/api/media/${m.id}`}
                    alt={m.filename}
                  />
                )}
              </a>
            ))}
          </div>
          {r.clarifications?.map((c: any, i: number) => (
            <p key={i}>
              {t("Citizen clarification")}: {c.note} · {time(c.at)}
            </p>
          ))}
          {r.reviewHistory?.map((v: any, i: number) => (
            <p className="text-sm" key={i}>
              {t(v.status)} · {v.note} · {v.reviewer} · {time(v.at)}
            </p>
          ))}
          {!!r.possibleDuplicates?.length && (
            <div role="note" className="rounded bg-amber-50 p-3">
              <b>{t("Possible duplicate reports")}</b>
              <p>{t("Duplicate review notice")}</p>
              {r.possibleDuplicates.map((d: any) => (
                <p key={d.id}>
                  <Link
                    className="underline"
                    to={`/response?reportId=${encodeURIComponent(d.id)}`}
                  >
                    {d.id}
                  </Link>{" "}
                  · {d.location} · {t(d.status)}
                </p>
              ))}
            </div>
          )}
          <label className="block">
            {t("Review note")}
            <Input
              aria-label={t("Review note")}
              className="mt-1 w-full"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </label>
          <div className="flex flex-wrap gap-2">
            {["Verified", "Rejected", "Clarification Requested"].map(
              (status) => (
                <Button
                  type="button"
                  key={status}
                  disabled={busy || closed || note.trim().length < 5}
                  variant="outline"
                  onClick={() =>
                    action(() =>
                      patch(`/api/reports/${r.id}/verify`, { status, note }),
                    )
                  }
                >
                  {t(
                    status === "Verified"
                      ? "Verify only"
                      : status === "Rejected"
                        ? "Reject"
                        : "Request clarification",
                  )}
                </Button>
              ),
            )}
          </div>
          {!active && !closed && (
            <>
              <h2 className="font-bold">{t("Confirm dispatch destination")}</h2>
              <p>{t("Destination confirmation notice")}</p>
              <div className="grid gap-3 md:grid-cols-2">
                <label>
                  {t("Destination latitude")}
                  <Input
                    aria-label={t("Destination latitude")}
                    type="number"
                    step="any"
                    min={-90}
                    max={90}
                    value={lat}
                    onChange={(e) => setDestination(e.target.value, lng)}
                  />
                </label>
                <label>
                  {t("Destination longitude")}
                  <Input
                    aria-label={t("Destination longitude")}
                    type="number"
                    step="any"
                    min={-180}
                    max={180}
                    value={lng}
                    onChange={(e) => setDestination(lat, e.target.value)}
                  />
                </label>
              </div>
              <LocationPicker
                value={{ lat, lng }}
                disabled={busy}
                onChange={setDestination}
              />
              {corrected && (
                <label className="block">
                  {t("Destination correction reason")}
                  <Input
                    aria-label={t("Destination correction reason")}
                    className="w-full"
                    value={correction}
                    onChange={(e) => setCorrection(e.target.value)}
                  />
                </label>
              )}
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={destinationConfirmed}
                  onChange={(e) => setDestinationConfirmed(e.target.checked)}
                />
                {t("I confirm this destination")}
              </label>
              {!teams.data ? (
                <p>{t("Loading…")}</p>
              ) : all.length === 0 ? (
                <p>{t("No teams configured")}</p>
              ) : available.length === 0 ? (
                <p>{t("All teams busy")}</p>
              ) : eligible.length === 0 ? (
                <p>{t("Outside configured team coverage")}</p>
              ) : (
                <>
                  <label className="block">
                    {t("Team")}
                    <Select
                      aria-label={t("Team")}
                      value={team}
                      onChange={(e) => {
                        setTeam(e.target.value);
                        setTeamConfirmed(false);
                      }}
                    >
                      <option value="">{t("Select team")}</option>
                      {eligible.map((v: any) => (
                        <option key={v.id} value={v.id}>
                          {v.name}
                        </option>
                      ))}
                    </Select>
                  </label>
                  <p>{t("Coverage confirmation notice")}</p>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={teamConfirmed}
                      onChange={(e) => setTeamConfirmed(e.target.checked)}
                    />
                    {t("I confirm this team")}
                  </label>
                </>
              )}
              <Button
                type="button"
                variant="outline"
                disabled={busy}
                onClick={() => setShowTeamSetup((v) => !v)}
              >
                {t("Register a team here")}
              </Button>
              {showTeamSetup && (
                <form
                  onSubmit={createTeam}
                  className="space-y-3 rounded-xl border p-4"
                >
                  <h3 className="font-bold">{t("Register a team here")}</h3>
                  <p>{t("Inline team setup notice")}</p>
                  <label className="block">
                    {t("Team name")}
                    <Input
                      className="w-full"
                      name="name"
                      aria-label={t("Team name")}
                      required
                      maxLength={200}
                    />
                  </label>
                  <label className="block">
                    {t("Team information source")}
                    <Input
                      className="w-full"
                      name="source"
                      aria-label={t("Team information source")}
                      required
                      minLength={3}
                      maxLength={1000}
                    />
                  </label>
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={practiceTeam}
                      onChange={(e) => setPracticeTeam(e.target.checked)}
                    />
                    {t("This is a practice team")}
                  </label>
                  <div className="flex gap-2">
                    <Button type="submit" disabled={busy}>
                      {t("Save team")}
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => setShowTeamSetup(false)}
                    >
                      {t("Cancel team setup")}
                    </Button>
                  </div>
                </form>
              )}
              {!verified && (
                <label className="block">
                  {t("Dispatch decision")}
                  <Select
                    aria-label={t("Dispatch decision")}
                    value={mode}
                    onChange={(e) => setMode(e.target.value)}
                  >
                    <option value="verify-and-assign">
                      {t("Verify and assign")}
                    </option>
                    <option value="urgent-unverified">
                      {t("Urgent unverified dispatch")}
                    </option>
                  </Select>
                </label>
              )}
              {!verified && mode === "urgent-unverified" && (
                <label className="block">
                  {t("Urgent dispatch reason")}
                  <Input
                    aria-label={t("Urgent dispatch reason")}
                    className="w-full"
                    value={urgentReason}
                    onChange={(e) => setUrgentReason(e.target.value)}
                  />
                </label>
              )}
              <Button
                disabled={
                  busy ||
                  !!report.error ||
                  !valid ||
                  !destinationConfirmed ||
                  !teamConfirmed ||
                  !eligible.some((v: any) => v.id === team) ||
                  note.trim().length < 5 ||
                  (corrected && correction.trim().length < 5) ||
                  (!verified &&
                    mode === "urgent-unverified" &&
                    urgentReason.trim().length < 10)
                }
                onClick={() =>
                  action(async () => {
                    await post(`/api/reports/${r.id}/dispatch`, {
                      teamId: team,
                      lat: Number(lat),
                      lng: Number(lng),
                      destinationConfirmed,
                      teamConfirmed,
                      note,
                      correctionReason: correction,
                      mode: verified ? "verify-and-assign" : mode,
                      urgentReason,
                    });
                    setTeam("");
                    setDestinationConfirmed(false);
                    setTeamConfirmed(false);
                  })
                }
              >
                {t(
                  !verified && mode === "urgent-unverified"
                    ? "Assign urgent investigation"
                    : "Verify and assign",
                )}
              </Button>
            </>
          )}
          <p>{t("Assignment progress notice")}</p>
          {r.deployments?.map((d: any) => (
            <Card className="p-3" key={d.id}>
              <p>
                {d.team} · {t(d.status)}
              </p>
              <p>
                {d.lat ?? d.reportCoordinates?.lat},{" "}
                {d.lng ?? d.reportCoordinates?.lng}
              </p>
              {d.urgentUnverified && (
                <p>
                  {t("Urgent unverified dispatch")}: {d.urgentReason}
                </p>
              )}
              {d.statusHistory?.map((h: any, i: number) => (
                <p key={i}>
                  {t(h.status)} · {time(h.at)}
                </p>
              ))}
              <div className="flex gap-2">
                {(
                  {
                    Assigned: ["En Route", "Cancelled"],
                    "En Route": ["On Site", "Cancelled"],
                    "On Site": ["Completed", "Cancelled"],
                  } as Record<string, string[]>
                )[d.status]?.map((status) => (
                  <Button
                    key={status}
                    disabled={busy}
                    onClick={() =>
                      action(() =>
                        post(`/api/deployments/${d.id}/status`, { status }),
                      )
                    }
                  >
                    {t(status)}
                  </Button>
                ))}
              </div>
            </Card>
          ))}
        </Card>
      )}
      <Button disabled={busy} variant="outline" onClick={() => action(refresh)}>
        {t("Refresh response")}
      </Button>
      <Link className="underline" to="/response">
        {t("Team setup and other responses")}
      </Link>
    </>
  );
}
