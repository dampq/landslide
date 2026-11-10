import {
  useEffect,
  useState,
  FormEvent,
  ReactNode,
  Children,
  cloneElement,
  isValidElement,
  ReactElement,
} from "react";
import { Link } from "react-router-dom";
import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  LineChart,
  Line,
} from "recharts";
import {
  Download,
  MapPin,
  RefreshCw,
  CheckCircle,
  AlertTriangle,
} from "lucide-react";
import { useApp } from "./App";
import {
  api,
  post,
  patch,
  useData,
  Row,
  time,
  Queued,
  queueList,
  queuePut,
  queueDelete,
  syncQueue,
  queueIsSyncing,
  Account,
} from "./lib";
import { Button, Card, Input, Select, Badge } from "./components/ui";

function Heading({
  title,
  sub,
  children,
}: {
  title: string;
  sub?: string;
  children?: ReactNode;
}) {
  const { t } = useApp();
  return (
    <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
      <div>
        <h1 className="text-2xl font-black text-slate-900 md:text-3xl">
          {t(title)}
        </h1>
        {sub && <p className="mt-2 max-w-3xl text-sm text-slate-600">{sub}</p>}
      </div>
      {children}
    </div>
  );
}
function Empty() {
  const { t } = useApp();
  return <p className="p-5 text-sm text-slate-500">{t("No records yet")}</p>;
}
function Load({
  query,
}: {
  query: { loading: boolean; error: string; refresh: () => void };
}) {
  const { t } = useApp();
  return query.error ? (
    <div className="error mb-4" role="alert">
      {query.error}{" "}
      <button className="underline" onClick={query.refresh}>
        {t("Try again")}
      </button>
    </div>
  ) : query.loading ? (
    <p role="status" className="p-4 text-slate-500">
      {t("Loading…")}
    </p>
  ) : null;
}
function Sample({ row }: { row: any }) {
  const { t } = useApp();
  return (
    <div className="mt-2 text-xs text-slate-500">
      {row.simulated && (
        <span className="sample mr-2">{t("Sample / simulated")}</span>
      )}
      {row.source && (
        <span>
          {t("Source")}: {row.source}
        </span>
      )}
    </div>
  );
}
function Risk({ value }: { value: string }) {
  const { t } = useApp();
  return (
    <Badge
      className={
        value === "Critical" || value === "Blocked"
          ? "bg-red-100 text-red-800"
          : value === "High"
            ? "bg-orange-100 text-orange-800"
            : "bg-blue-50 text-blue-900"
      }
    >
      {t(value)}
    </Badge>
  );
}
function useAction() {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [message, setMessage] = useState("");
  async function run(fn: () => Promise<any>, success = "Saved") {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await fn();
      setMessage(success);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return { busy, error, message, run };
}
function Result({ job }: { job: ReturnType<typeof useAction> }) {
  const { t } = useApp();
  return (
    <>
      {job.error && (
        <p className="error my-3" role="alert">
          {job.error}
        </p>
      )}
      {job.message && (
        <p className="success my-3" role="status">
          {t(job.message)}
        </p>
      )}
    </>
  );
}
function Field({ label, children }: { label: string; children: ReactNode }) {
  const { t } = useApp();
  return (
    <label className="field">
      {t(label)}
      {Children.map(children, (child) =>
        isValidElement(child) &&
        (child.type === Input ||
          child.type === Select ||
          child.type === "textarea")
          ? cloneElement(child as ReactElement<any>, {
              "aria-label": (child.props as any)["aria-label"] || t(label),
            })
          : child,
      )}
    </label>
  );
}
function Export({ kind }: { kind: string }) {
  const { t } = useApp();
  return (
    <a
      className="inline-flex items-center gap-2 rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm font-semibold"
      href={"/api/export/" + kind}
      download
    >
      <Download size={16} />
      {t("Download CSV")}
    </a>
  );
}
function Chart({ data, line = false }: { data: any[]; line?: boolean }) {
  if (!data.length) return <Empty />;
  return (
    <div className="mt-4 h-64 min-w-0">
      <ResponsiveContainer width="100%" height="100%">
        {line ? (
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" fontSize={11} />
            <YAxis />
            <Tooltip />
            <Line
              type="monotone"
              dataKey="count"
              stroke="#2563eb"
              dot={false}
            />
          </LineChart>
        ) : (
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" fontSize={11} />
            <YAxis allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="count" fill="#2563eb" radius={[6, 6, 0, 0]} />
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}

export function Dashboard() {
  const { account, t } = useApp();
  const query = useData("/api/dashboard"),
    notifications = useData("/api/records/notifications");
  const job = useAction();
  const names: Record<string, string> = {
    locations: "Locations",
    reports: "Reports",
    publishedAlerts: "Published",
    sensors: "Sensors",
    roads: "Roads",
    villages: "Villages & population",
  };
  return (
    <>
      <Heading
        title="Dashboard"
        sub={`${account?.name} · ${new Date().toLocaleDateString()}`}
      />
      <Load query={query} />
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-3">
        {Object.entries(names).map(([key, label]) => (
          <Card className="p-5" key={key}>
            <div className="text-sm text-slate-500">{t(label)}</div>
            <strong className="mt-2 block text-3xl">
              {query.data?.counts[key] ?? "—"}
            </strong>
            <div className="mt-2 text-xs text-slate-500">Stored records</div>
          </Card>
        ))}
      </div>
      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Card className="p-5">
          <h2 className="font-bold">{t("Field data")}</h2>
          <p className="my-3 text-sm text-slate-600">{query.data?.notice}</p>
          <p className="text-sm">
            Labelled sample records: {query.data?.sampleRecords ?? "—"}
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Link
              className="rounded-xl bg-blue-700 px-4 py-2 text-sm font-bold text-white"
              to="/reports"
            >
              {t("New incident report")}
            </Link>
            <Link className="rounded-xl border px-4 py-2 text-sm" to="/map">
              {t("GIS map")}
            </Link>
          </div>
        </Card>
        <Card className="p-5">
          <h2 className="font-bold">{t("Model integration")}</h2>
          <p className="mt-3 text-sm text-slate-600">
            {query.data?.modelConfigured
              ? "Model path configured; verify availability in the model portal."
              : "The external Random Forest model has not been supplied. No ML probabilities are fabricated."}
          </p>
          <p className="mt-3 text-sm text-slate-600">
            No satellite or physical sensor feed is claimed to be live.
            OpenStreetMap and weather access depend on network availability.
          </p>
        </Card>
      </div>
      <Card className="mt-5 p-5">
        <h2 className="font-bold">{t("Notifications")}</h2>
        <Load query={notifications} />
        <Result job={job} />
        {notifications.data?.items.length === 0 && <Empty />}
        {notifications.data?.items.map((n: Row) => (
          <div key={n.id} className="mt-3 rounded-xl border p-4">
            <b>{n.name}</b>
            <p className="my-2 text-sm">{n.description}</p>
            <p className="text-sm font-semibold">{n.action}</p>
            <Sample row={n} />
            {n.read ? (
              <span className="text-xs">{t("Read")}</span>
            ) : (
              <Button
                className="mt-2"
                variant="outline"
                disabled={job.busy}
                onClick={() =>
                  job.run(async () => {
                    await post(`/api/notifications/${n.id}/read`);
                    await notifications.refresh();
                  })
                }
              >
                {t("Mark read")}
              </Button>
            )}
          </div>
        ))}
      </Card>
    </>
  );
}

function ReportCard({
  row,
  refresh,
}: {
  row: Row;
  refresh: () => Promise<void>;
}) {
  const { account, t } = useApp();
  const [note, setNote] = useState(""),
    [media, setMedia] = useState<any[] | null>(null);
  const job = useAction();
  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <b>
            {row.incident} · {row.location}
          </b>
          <p className="mt-1 text-xs text-slate-500">
            {time(row.createdAt)} · {row.reporterRole}
          </p>
        </div>
        <Risk value={row.status} />
      </div>
      <p className="my-3 whitespace-pre-wrap text-sm">{row.description}</p>
      <p className="text-xs text-slate-500">
        GPS: {row.lat}, {row.lng}
      </p>
      {row.verificationNote && (
        <p className="mt-3 rounded-lg bg-blue-50 p-3 text-sm">
          {t("Review")}: {row.verificationNote} · {row.verifiedBy}
        </p>
      )}
      <Sample row={row} />
      <Button
        variant="outline"
        className="mt-3"
        disabled={job.busy}
        onClick={() =>
          job.run(async () => {
            setMedia((await api(`/api/reports/${row.id}/media`)).items);
          }, "")
        }
      >
        {t("Photographs / videos")}
      </Button>
      {media && (
        <div className="mt-3 space-y-2">
          {media.length === 0 && <Empty />}
          {media.map((m) => (
            <div key={m.id} className="rounded-lg border p-3 text-sm">
              <a
                className="text-blue-700 underline"
                href={"/api/media/" + m.id}
                download
              >
                {m.filename}
              </a>
              {m.processing.width && (
                <p className="mt-2 text-xs">
                  OpenCV: {m.processing.width} × {m.processing.height} px ·
                  brightness {m.processing.brightness} · sharpness{" "}
                  {m.processing.sharpness} · edge fraction{" "}
                  {m.processing.edgeFraction}
                  <br />
                  {m.processing.classification}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
      {account?.role !== "citizen" &&
        !["Resolved", "Rejected"].includes(row.status) && (
          <div className="mt-4 border-t pt-4">
            <Field label="Review note">
              <Input
                value={note}
                onChange={(e) => setNote(e.target.value)}
                minLength={5}
              />
            </Field>
            <div className="mt-3 flex flex-wrap gap-2">
              {(row.status === "Verified"
                ? ["Resolved"]
                : ["Verified", "Rejected"]
              ).map((status) => (
                <Button
                  key={status}
                  disabled={job.busy || note.trim().length < 5}
                  variant={status === "Rejected" ? "danger" : "default"}
                  onClick={() =>
                    job.run(async () => {
                      await patch(`/api/reports/${row.id}/verify`, {
                        status,
                        note,
                      });
                      await refresh();
                    })
                  }
                >
                  {t(
                    status === "Verified"
                      ? "Verify"
                      : status === "Rejected"
                        ? "Reject"
                        : "Resolve",
                  )}
                </Button>
              ))}
            </div>
          </div>
        )}
      <Result job={job} />
    </Card>
  );
}
export function Reports() {
  const { account, t, online } = useApp();
  const query = useData("/api/records/reports");
  const job = useAction();
  const [files, setFiles] = useState<File[]>([]),
    [gps, setGps] = useState({ lat: "", lng: "" }),
    [message, setMessage] = useState("");
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    await job.run(async () => {
      if (files.length > 5 || files.some((f) => f.size > 10_000_000))
        throw new Error("Up to 5 files, each under 10 MB.");
      const report = {
        clientId: crypto.randomUUID(),
        incident: values.incident,
        location: values.location,
        lat: Number(values.lat),
        lng: Number(values.lng),
        severity: values.severity,
        description: values.description,
      };
      if (
        !Number.isFinite(report.lat) ||
        !Number.isFinite(report.lng) ||
        Math.abs(report.lat) > 90 ||
        Math.abs(report.lng) > 180
      )
        throw new Error("Enter valid GPS coordinates.");
      await queuePut({
        key: report.clientId,
        userId: account!.id,
        report,
        files,
        created: Date.now(),
      });
      setMessage(t("Report saved to this device"));
      form.reset();
      setFiles([]);
      setGps({ lat: "", lng: "" });
      if (online) {
        try {
          await syncQueue(account!.id);
          setMessage(t("Report sent"));
          await query.refresh();
        } catch (e) {
          setMessage(
            t("Report saved to this device") + " — " + (e as Error).message,
          );
        }
      }
    }, "");
  }
  return (
    <>
      <Heading title="Reports" sub={t("Remember to stay safe")} />
      <Card className="mb-6 p-5">
        <h2 className="mb-4 text-lg font-bold">{t("New incident report")}</h2>
        <form onSubmit={submit} className="grid gap-4 md:grid-cols-2">
          <Field label="Incident type">
            <Select name="incident" required>
              {[
                "Ground Crack",
                "Small Landslide",
                "Major Landslide",
                "Road Blockage",
                "Slope Movement",
                "Flooding",
                "Damaged Bridge",
                "Other",
              ].map((v) => (
                <option key={v}>{v}</option>
              ))}
            </Select>
          </Field>
          <Field label="Severity">
            <Select name="severity">
              {["Low", "Moderate", "High", "Critical"].map((v) => (
                <option key={v} value={v}>
                  {t(v)}
                </option>
              ))}
            </Select>
          </Field>
          <div className="md:col-span-2">
            <Field label="Location">
              <Input name="location" required minLength={2} maxLength={200} />
            </Field>
          </div>
          <Field label="Latitude">
            <Input
              name="lat"
              type="number"
              step="any"
              required
              min={-90}
              max={90}
              value={gps.lat}
              onChange={(e) => setGps({ ...gps, lat: e.target.value })}
            />
          </Field>
          <Field label="Longitude">
            <Input
              name="lng"
              type="number"
              step="any"
              required
              min={-180}
              max={180}
              value={gps.lng}
              onChange={(e) => setGps({ ...gps, lng: e.target.value })}
            />
          </Field>
          <Button
            type="button"
            variant="outline"
            onClick={() =>
              job.run(
                () =>
                  new Promise<void>((resolve, reject) => {
                    if (!navigator.geolocation) {
                      reject(new Error("Geolocation is unavailable"));
                      return;
                    }
                    navigator.geolocation.getCurrentPosition(
                      (p) => {
                        setGps({
                          lat: p.coords.latitude.toFixed(6),
                          lng: p.coords.longitude.toFixed(6),
                        });
                        resolve();
                      },
                      (e) => reject(new Error(e.message)),
                      { enableHighAccuracy: true, timeout: 15000 },
                    );
                  }),
                "",
              )
            }
          >
            <MapPin size={16} />
            {t("Use my GPS")}
          </Button>
          <div className="md:col-span-2">
            <Field label="Description">
              <textarea
                name="description"
                required
                minLength={10}
                maxLength={4000}
              />
            </Field>
          </div>
          <div className="md:col-span-2">
            <Field label="Photographs / videos">
              <Input
                aria-label={t("Photographs / videos")}
                type="file"
                accept="image/png,image/jpeg,image/webp,video/mp4"
                multiple
                onChange={(e) => setFiles(Array.from(e.target.files || []))}
              />
              <small>
                JPEG, PNG, WebP, MP4 · 5 files maximum · 10 MB each. Files are
                stored with your report, including offline.
              </small>
            </Field>
          </div>
          <label className="flex items-center gap-2 text-sm md:col-span-2">
            <input type="checkbox" required />
            {t("Confirm observations")}
          </label>
          <Button disabled={job.busy} type="submit">
            {job.busy ? t("Loading…") : t("Submit report")}
          </Button>
        </form>
        <Result job={job} />
        {message && (
          <p className="success mt-3" role="status">
            {message}
          </p>
        )}
      </Card>
      <Heading
        title={
          account?.role === "citizen" ? "My reports" : "Verification queue"
        }
      >
        <Button variant="outline" onClick={query.refresh}>
          {t("Refresh")}
        </Button>
      </Heading>
      <Load query={query} />
      <div className="space-y-4">
        {query.data?.items.length === 0 && <Empty />}
        {query.data?.items.map((r: Row) => (
          <ReportCard key={r.id} row={r} refresh={query.refresh} />
        ))}
      </div>
    </>
  );
}

type FieldDef = {
  key: string;
  label: string;
  type?: string;
  options?: string[];
  required?: boolean;
};
const locationFields: FieldDef[] = [
  { key: "name", label: "Name", required: true },
  { key: "district", label: "District", required: true },
  { key: "state", label: "State", required: true },
  { key: "lat", label: "Latitude", type: "number", required: true },
  { key: "lng", label: "Longitude", type: "number", required: true },
  {
    key: "level",
    label: "Severity",
    options: ["Low", "Moderate", "High", "Critical"],
  },
  { key: "slope", label: "Slope (degrees)", type: "number" },
];
const commonCoords: FieldDef[] = [
  { key: "name", label: "Name", required: true },
  { key: "lat", label: "Latitude", type: "number", required: true },
  { key: "lng", label: "Longitude", type: "number", required: true },
];
const fieldDefs: Record<string, FieldDef[]> = {
  locations: locationFields,
  roads: [
    ...commonCoords,
    { key: "route", label: "Route" },
    {
      key: "status",
      label: "Status",
      options: ["Open", "Partially Blocked", "Blocked", "Under Verification"],
      required: true,
    },
  ],
  villages: [
    ...commonCoords,
    {
      key: "population",
      label: "Population count",
      type: "number",
      required: true,
    },
    { key: "year", label: "Dataset year", type: "number", required: true },
    {
      key: "resolutionM",
      label: "Grid resolution (metres)",
      type: "number",
      required: true,
    },
    { key: "license", label: "Dataset license", required: true },
  ],
  infrastructure: [
    ...commonCoords,
    { key: "type", label: "Infrastructure type", required: true },
  ],
  history: [
    ...commonCoords,
    {
      key: "observedAt",
      label: "Event time (UTC Unix seconds)",
      type: "number",
      required: true,
    },
    { key: "description", label: "Description" },
  ],
  satellite: [
    ...commonCoords,
    {
      key: "url",
      label: "Public imagery URL (HTTPS)",
      type: "url",
      required: true,
    },
    { key: "description", label: "Description" },
  ],
  teams: [{ key: "name", label: "Name", required: true }],
  alerts: [
    { key: "name", label: "Name", required: true },
    {
      key: "severity",
      label: "Severity",
      options: ["Low", "Moderate", "High", "Critical"],
      required: true,
    },
    { key: "description", label: "Description", required: true },
    { key: "action", label: "Action", required: true },
  ],
};
function RecordForm({
  kind,
  refresh,
  editing,
  onClose,
}: {
  kind: string;
  refresh: () => Promise<void>;
  editing?: Row;
  onClose?: () => void;
}) {
  const { t } = useApp();
  const job = useAction();
  const [simulated, setSimulated] = useState(editing?.simulated ?? true);
  const locs = useData("/api/records/locations");
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const values = Object.fromEntries(new FormData(form));
    await job.run(async () => {
      const data: any = { ...values, simulated };
      for (const f of fieldDefs[kind])
        if (f.type === "number") {
          if (values[f.key] === "") delete data[f.key];
          else data[f.key] = Number(values[f.key]);
        }
      if (editing) await patch(`/api/records/${kind}/${editing.id}`, data);
      else await post("/api/records/" + kind, data);
      await refresh();
      if (onClose) onClose();
      else form.reset();
    });
  }
  return (
    <Card className="my-4 p-5">
      <h2 className="mb-4 font-bold">
        {t(editing ? "Review" : "Create")} · {kind}
      </h2>
      <form className="grid gap-4 md:grid-cols-2" onSubmit={submit}>
        {fieldDefs[kind].map((f) => (
          <Field key={f.key} label={f.label}>
            {f.options ? (
              <Select
                name={f.key}
                required={f.required}
                defaultValue={editing?.[f.key] ?? f.options[0]}
              >
                {f.options.map((v) => (
                  <option key={v} value={v}>
                    {t(v)}
                  </option>
                ))}
              </Select>
            ) : (
              <Input
                name={f.key}
                type={f.type || "text"}
                step={f.type === "number" ? "any" : undefined}
                maxLength={2000}
                required={f.required}
                defaultValue={editing?.[f.key] ?? ""}
              />
            )}
          </Field>
        ))}
        {kind === "alerts" && (
          <Field label="Location">
            <Select name="locationId" required>
              <option value="">{t("Select location")}</option>
              {locs.data?.items.map((r: Row) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </Select>
          </Field>
        )}
        <Field label="Source">
          <Input
            name="source"
            required
            maxLength={500}
            defaultValue={editing?.source || "Synthetic demonstration"}
          />
        </Field>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={simulated}
            onChange={(e) => setSimulated(e.target.checked)}
          />
          {t("Sample / simulated")}
        </label>
        <div className="flex gap-3 md:col-span-2">
          <Button type="submit" disabled={job.busy}>
            {t("Save")}
          </Button>
          {onClose && (
            <Button type="button" variant="outline" onClick={onClose}>
              Close
            </Button>
          )}
        </div>
      </form>
      <Result job={job} />
    </Card>
  );
}
function RecordList({
  kind,
  title,
  editable = true,
}: {
  kind: string;
  title: string;
  editable?: boolean;
}) {
  const { account, t } = useApp();
  const [search, setSearch] = useState(""),
    [show, setShow] = useState(false),
    [editing, setEditing] = useState<Row | undefined>();
  const query = useData(
    "/api/records/" + kind + "?q=" + encodeURIComponent(search),
  );
  const canEdit = account?.role !== "citizen" && editable;
  return (
    <>
      <div className="my-5 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-bold">{t(title)}</h2>
        <div className="flex flex-wrap gap-2">
          <Input
            aria-label={t("Search")}
            className="max-w-44"
            placeholder={t("Search")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {account?.role !== "citizen" && <Export kind={kind} />}
          <Button variant="outline" onClick={query.refresh}>
            {t("Refresh")}
          </Button>
          {canEdit && (
            <Button
              onClick={() => {
                setEditing(undefined);
                setShow(!show);
              }}
            >
              {t("Create")}
            </Button>
          )}
        </div>
      </div>
      {show && canEdit && (
        <RecordForm
          key={editing?.id || kind}
          kind={kind}
          refresh={query.refresh}
          editing={editing}
          onClose={() => setShow(false)}
        />
      )}
      <Load query={query} />
      {query.data?.items.length === 0 && <Empty />}
      <div className="record-grid">
        {query.data?.items.map((r: Row) => (
          <Card key={r.id} className="p-5">
            <div className="flex items-center justify-between gap-2">
              <b>{r.name || r.location || r.id}</b>
              {(r.level || r.status) && <Risk value={r.level || r.status} />}
            </div>
            <dl className="mt-3 space-y-1 text-sm">
              {Object.entries(r)
                .filter(
                  ([k, v]) =>
                    ![
                      "id",
                      "kind",
                      "name",
                      "source",
                      "simulated",
                      "updatedAt",
                      "createdAt",
                      "lat",
                      "lng",
                      "status",
                      "level",
                    ].includes(k) && typeof v !== "object",
                )
                .map(([k, v]) => (
                  <div key={k} className="flex flex-wrap justify-between gap-2">
                    <dt className="text-slate-500">{k}</dt>
                    <dd className="max-w-full break-words">{String(v)}</dd>
                  </div>
                ))}
            </dl>
            {r.lat != null && (
              <p className="mt-2 text-xs text-slate-500">
                GPS {r.lat}, {r.lng}
              </p>
            )}
            <Sample row={r} />
            <p className="mt-2 text-xs text-slate-400">{time(r.updatedAt)}</p>
            {canEdit && kind !== "teams" && (
              <Button
                variant="outline"
                className="mt-3"
                onClick={() => {
                  setEditing(r);
                  setShow(true);
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}
              >
                {t("Review")}
              </Button>
            )}
          </Card>
        ))}
      </div>
      {query.data?.total > 100 && (
        <p className="mt-3 text-sm">
          Showing the first 100 matches; narrow the search. CSV exports include
          up to 10,000 records.
        </p>
      )}
    </>
  );
}
export function Monitoring() {
  const { account, t } = useApp();
  const [tab, setTab] = useState("locations");
  const job = useAction();
  const [version, setVersion] = useState(0);
  const tabs = [
    ["locations", "Locations"],
    ["sensors", "Sensors"],
    ["roads", "Roads"],
    ["villages", "Villages & population"],
    ["infrastructure", "Infrastructure"],
  ];
  return (
    <>
      <Heading
        title="Monitoring"
        sub="Stored environmental observations and geographic records. Sample risk levels are not model predictions."
      />
      <div className="flex flex-wrap gap-2">
        {tabs.map(([key, name]) => (
          <Button
            key={key}
            variant={tab === key ? "default" : "outline"}
            onClick={() => setTab(key)}
          >
            {t(name)}
          </Button>
        ))}
      </div>
      {tab === "sensors" && (
        <Card className="mt-4 p-4">
          <p className="mb-3 text-sm">
            This simulator generates rainfall, soil-moisture and ground-movement
            demonstration readings only. It does not contact physical sensors,
            run predictions or issue warnings.
          </p>
          {account?.role !== "citizen" && (
            <Button
              disabled={job.busy}
              onClick={() =>
                job.run(async () => {
                  await post("/api/sensors/simulate");
                  setVersion((v) => v + 1);
                })
              }
            >
              {t("Run sensor simulation")}
            </Button>
          )}
          <Result job={job} />
        </Card>
      )}
      <RecordList
        key={tab + version}
        kind={tab}
        title={tabs.find((t) => t[0] === tab)![1]}
        editable={tab !== "sensors"}
      />
    </>
  );
}

function Exposure({ locationId }: { locationId: string }) {
  const [radius, setRadius] = useState(5000);
  const query = useData("/api/exposure/" + locationId + "?radius=" + radius);
  const { t } = useApp();
  return (
    <Card className="mt-5 p-5">
      <h2 className="font-bold">{t("Population exposure")}</h2>
      <div className="mt-3 max-w-xs">
        <Field label="Radius (metres)">
          <Select
            value={radius}
            onChange={(e) => setRadius(Number(e.target.value))}
          >
            {[1000, 5000, 10000, 25000].map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <Load query={query} />
      {query.data && (
        <>
          <p className="my-3 text-3xl font-black">
            ≈{" "}
            {query.data.approximatePopulation?.toLocaleString() ??
              "Unavailable"}
          </p>
          <p className="text-sm text-slate-600">{query.data.method}</p>
          <Sample
            row={{
              simulated: query.data.simulated,
              source: query.data.sources.join("; "),
            }}
          />
          <p className="mt-3 text-sm">
            Nearby geographic records: {query.data.items.length}
          </p>
        </>
      )}
    </Card>
  );
}
export function MapPage() {
  const { t } = useApp();
  const [layers, setLayers] = useState([
    "locations",
    "roads",
    "villages",
    "infrastructure",
    "history",
    "sensors",
  ]);
  const query = useData("/api/gis?layers=" + layers.join(","));
  const [selected, setSelected] = useState("");
  const color = (p: any) =>
    p.level === "Critical" || p.status === "Blocked"
      ? "#dc2626"
      : p.kind === "history"
        ? "#9333ea"
        : p.kind === "villages"
          ? "#16a34a"
          : "#2563eb";
  return (
    <>
      <Heading
        title="GIS map"
        sub="Layer switches filter stored PostGIS features. The map uses OpenStreetMap; base tiles need network access."
      />
      <div className="mb-4 flex flex-wrap gap-4">
        {[
          "locations",
          "roads",
          "villages",
          "infrastructure",
          "history",
          "sensors",
          "satellite",
        ].map((l) => (
          <label key={l} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={layers.includes(l)}
              onChange={() =>
                setLayers((v) =>
                  v.includes(l) ? v.filter((x) => x !== l) : [...v, l],
                )
              }
            />
            {l}
          </label>
        ))}
      </div>
      <Load query={query} />
      <Card className="overflow-hidden">
        <div className="h-[540px] max-h-[70vh]">
          <MapContainer center={[25.9, 92.5]} zoom={6} scrollWheelZoom>
            <TileLayer
              attribution="&copy; OpenStreetMap contributors"
              url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            {query.data?.features.map((f: any) => {
              const p = f.properties;
              return (
                <CircleMarker
                  key={p.id}
                  center={[
                    f.geometry.coordinates[1],
                    f.geometry.coordinates[0],
                  ]}
                  radius={p.kind === "locations" ? 12 : 7}
                  pathOptions={{ color: color(p), fillOpacity: 0.7 }}
                >
                  <Popup>
                    <b>{p.name}</b>
                    <p>
                      {p.kind} · {p.status || p.level || ""}
                    </p>
                    <Sample row={p} />
                    {p.kind === "locations" && (
                      <button
                        className="mt-3 rounded bg-blue-700 p-2 text-white"
                        onClick={() => setSelected(p.id)}
                      >
                        {t("Population exposure")}
                      </button>
                    )}
                  </Popup>
                </CircleMarker>
              );
            })}
          </MapContainer>
        </div>
      </Card>
      <p className="mt-3 text-xs text-slate-500">
        Red: critical / blocked · Purple: historical records · Green: population
        points · Blue: other records. Roads are representative points, not
        surveyed road geometries.
      </p>
      {selected && <Exposure locationId={selected} />}
    </>
  );
}

function LocationSelect({
  value,
  onChange,
}: {
  value: string;
  onChange: (v: string) => void;
}) {
  const query = useData("/api/records/locations");
  const { t } = useApp();
  return (
    <div className="mb-5 max-w-lg">
      <Field label="Location">
        <Select
          required
          value={value}
          onChange={(e) => onChange(e.target.value)}
        >
          <option value="">{t("Select location")}</option>
          {query.data?.items.map((r: Row) => (
            <option key={r.id} value={r.id}>
              {r.name} · {r.state}
            </option>
          ))}
        </Select>
      </Field>
      <Load query={query} />
    </div>
  );
}
function Forecast({ id }: { id: string }) {
  const query = useData("/api/weather/" + id);
  const { account, t } = useApp();
  const job = useAction();
  return (
    <>
      <div className="flex items-center gap-3">
        {account?.role !== "citizen" && (
          <Button
            disabled={job.busy}
            onClick={() =>
              job.run(async () => {
                await post(`/api/weather/${id}/refresh`);
                await query.refresh();
              })
            }
          >
            <RefreshCw size={16} />
            {t("Refresh forecast")}
          </Button>
        )}
        <Button variant="outline" onClick={query.refresh}>
          {t("Refresh")}
        </Button>
      </div>
      <Result job={job} />
      <Load query={query} />
      {query.data?.available ? (
        <>
          <div className="mt-5 grid gap-4 sm:grid-cols-3">
            {[
              ["Modelled past 24h", query.data.rainfall24h],
              ["Modelled past 72h", query.data.rainfall72h],
              ["Forecast next 24h", query.data.forecast24h],
            ].map(([n, v]) => (
              <Card className="p-5" key={n}>
                <div className="text-sm text-slate-500">{n}</div>
                <strong className="text-3xl">
                  {v == null ? "Unavailable" : Number(v).toFixed(1) + " mm"}
                </strong>
              </Card>
            ))}
          </div>
          <Card className="mt-5 p-5">
            <b>Hourly rainfall (mm)</b>
            <Chart
              line
              data={query.data.hourly.map((h: any) => ({
                name: h.time.slice(5).replace("T", " "),
                count: h.rainfall,
              }))}
            />
            <p className="text-sm">{query.data.attribution}</p>
            <p className="mt-2 text-xs">
              Updated: {time(query.data.updatedAt)} ·{" "}
              {query.data.stale ? "Stale (over one hour old)" : "Fresh cache"}
            </p>
            <Sample row={query.data} />
          </Card>
        </>
      ) : (
        <Card className="mt-5 p-5">
          {query.data?.message || t("No cached forecast")}
        </Card>
      )}
    </>
  );
}
export function Weather() {
  const [id, setId] = useState("");
  return (
    <>
      <Heading
        title="Weather"
        sub="Open-Meteo modelled rainfall and forecasts. Provider failures retain the last cache; no sample values are substituted."
      />
      <LocationSelect value={id} onChange={setId} />
      {id && <Forecast key={id} id={id} />}
    </>
  );
}

export function Prediction() {
  const { t } = useApp();
  const query = useData("/api/model"),
    history = useData("/api/records/predictions");
  const [id, setId] = useState("");
  const job = useAction();
  const [result, setResult] = useState<any>(null);
  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const values = Object.fromEntries(new FormData(e.currentTarget));
    const inputs = Object.fromEntries(
      query.data.features.map((f: any) => [f.name, Number(values[f.name])]),
    );
    await job.run(async () => {
      setResult(
        await post("/api/predictions", {
          locationId: id,
          observedAt: new Date(String(values.observedAt)).getTime() / 1000,
          source: values.source,
          inputs,
        }),
      );
      await history.refresh();
    }, "");
  }
  return (
    <>
      <Heading
        title="Model integration"
        sub="Inference only: the Random Forest model is supplied, trained and evaluated by the separate model team."
      />
      <Load query={query} />
      {query.data && !query.data.available && (
        <div className="mb-5 rounded-xl border border-amber-200 bg-amber-50 p-4">
          <b>{t("No model supplied")}</b>
          <p className="mt-2 text-sm">{query.data.message}</p>
        </div>
      )}
      <Card className="p-5">
        <LocationSelect value={id} onChange={setId} />
        <form onSubmit={submit} className="grid gap-4 md:grid-cols-2">
          {query.data?.features.map((f: any) => (
            <Field key={f.name} label={`${f.name} (${f.unit})`}>
              <Input
                name={f.name}
                type="number"
                step="any"
                min={f.min}
                max={f.max}
                required
              />
            </Field>
          ))}
          <Field label="Observation time">
            <Input name="observedAt" type="datetime-local" required />
          </Field>
          <Field label="Source">
            <Input name="source" required minLength={3} />
          </Field>
          <Button
            type="submit"
            disabled={job.busy || !query.data?.available || !id}
          >
            {t("Submit prediction")}
          </Button>
        </form>
        <Result job={job} />
        {result && (
          <div className="success mt-4">
            <b>
              {(result.probability * 100).toFixed(1)}% · model{" "}
              {result.modelVersion}
            </b>
            <p>{result.notice}</p>
          </div>
        )}
      </Card>
      <RecordList
        kind="predictions"
        title="Prediction history"
        editable={false}
      />
    </>
  );
}

export function Alerts() {
  const { account, t } = useApp();
  const query = useData("/api/records/alerts");
  const [show, setShow] = useState(false);
  const [note, setNote] = useState("");
  const job = useAction();
  return (
    <>
      <Heading
        title="Alerts"
        sub="Warnings follow draft → review → publication. Publication creates in-app notifications only; no SMS is sent."
      >
        {account?.role !== "citizen" && (
          <Button onClick={() => setShow(!show)}>{t("Create")}</Button>
        )}
      </Heading>
      {show && (
        <RecordForm
          kind="alerts"
          refresh={query.refresh}
          onClose={() => setShow(false)}
        />
      )}
      <Load query={query} />
      <Result job={job} />
      {account?.role !== "citizen" && (
        <div className="mb-5 max-w-xl">
          <Field label="Review note">
            <Input value={note} onChange={(e) => setNote(e.target.value)} />
          </Field>
        </div>
      )}
      <div className="space-y-4">
        {query.data?.items.length === 0 && <Empty />}
        {query.data?.items.map((r: Row) => (
          <Card key={r.id} className="border-l-4 border-l-orange-400 p-5">
            <div className="flex flex-wrap justify-between gap-2">
              <b>{r.name}</b>
              <div className="flex gap-2">
                <Risk value={r.severity} />
                <Risk value={r.status} />
              </div>
            </div>
            <p className="my-3 text-sm">{r.description}</p>
            <p className="text-sm font-bold">{r.action}</p>
            <Sample row={r} />
            {r.reviewNote && (
              <p className="mt-3 text-xs">
                {t("Review")}: {r.reviewNote} · {r.reviewedBy}
              </p>
            )}
            {account?.role !== "citizen" &&
              ["Draft", "Approved", "Published"].includes(r.status) && (
                <Button
                  className="mt-4"
                  disabled={job.busy || note.trim().length < 5}
                  onClick={() =>
                    job.run(async () => {
                      await post(
                        `/api/alerts/${r.id}/${r.status === "Draft" ? "approve" : r.status === "Approved" ? "publish" : "resolve"}`,
                        { note },
                      );
                      await query.refresh();
                    })
                  }
                >
                  {t(
                    r.status === "Draft"
                      ? "Approve"
                      : r.status === "Approved"
                        ? "Publish"
                        : "Resolve",
                  )}
                </Button>
              )}
          </Card>
        ))}
      </div>
    </>
  );
}

export function ResponsePage() {
  const { t } = useApp();
  const priorities = useData("/api/response/priorities"),
    teams = useData("/api/records/teams"),
    deployments = useData("/api/records/deployments");
  const [id, setId] = useState(""),
    [team, setTeam] = useState(""),
    [show, setShow] = useState(false);
  const job = useAction();
  const refresh = async () => {
    await Promise.all([
      priorities.refresh(),
      teams.refresh(),
      deployments.refresh(),
    ]);
  };
  return (
    <>
      <Heading
        title="Response"
        sub="Planning scores combine reviewed risk levels, approximate exposure and blocked roads. They are not ML predictions."
      />
      <Load query={priorities} />
      <div className="record-grid">
        {priorities.data?.items.map((r: Row) => (
          <Card key={r.id} className="p-5">
            <div className="flex justify-between">
              <b>{r.name}</b>
              <strong>{r.priorityScore}/100</strong>
            </div>
            <p className="my-3 text-sm">
              ≈ {r.exposure ?? "unknown"} people · {r.blockedRoads} blocked
              roads
            </p>
            <Risk value={r.level || "Low"} />
            <Sample row={r} />
            <Button
              className="mt-3"
              variant={id === r.id ? "default" : "outline"}
              onClick={() => setId(r.id)}
            >
              {t("Select location")}
            </Button>
          </Card>
        ))}
      </div>
      <Card className="my-5 p-5">
        <h2 className="mb-4 font-bold">{t("Deploy")}</h2>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            void job.run(async () => {
              await post("/api/deployments", { locationId: id, teamId: team });
              setTeam("");
              await refresh();
            });
          }}
          className="flex flex-wrap items-end gap-3"
        >
          <div className="flex-1">
            <LocationSelect value={id} onChange={setId} />
          </div>
          <Field label="Team">
            <Select
              required
              value={team}
              onChange={(e) => setTeam(e.target.value)}
            >
              <option value="">{t("Team")}</option>
              {teams.data?.items
                .filter((r: Row) => r.status === "Available")
                .map((r: Row) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
            </Select>
          </Field>
          <Button disabled={job.busy || !id || !team} type="submit">
            {t("Deploy")}
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={() => setShow(!show)}
          >
            {t("Create")} {t("Team")}
          </Button>
        </form>
        <Result job={job} />
      </Card>
      {show && (
        <RecordForm
          kind="teams"
          refresh={refresh}
          onClose={() => setShow(false)}
        />
      )}
      <Load query={deployments} />
      <div className="space-y-3">
        {deployments.data?.items.map((r: Row) => (
          <Card key={r.id} className="p-4">
            <b>
              {r.team} → {r.location}
            </b>
            <div className="my-3">
              <Risk value={r.status} />
            </div>
            <Sample row={r} />
            <div className="mt-3 flex gap-2">
              {(
                (
                  {
                    "En Route": ["On Site", "Cancelled"],
                    "On Site": ["Completed", "Cancelled"],
                  } as Record<string, string[]>
                )[r.status] || []
              ).map((status) => (
                <Button
                  key={status}
                  disabled={job.busy}
                  variant="outline"
                  onClick={() =>
                    job.run(async () => {
                      await post(`/api/deployments/${r.id}/status`, { status });
                      await refresh();
                    })
                  }
                >
                  {t(status)}
                </Button>
              ))}
            </div>
          </Card>
        ))}
      </div>
    </>
  );
}

export function History() {
  const [tab, setTab] = useState("history");
  const { t } = useApp();
  const sources = useData("/api/sources");
  return (
    <>
      <Heading
        title="History & imagery"
        sub="Historical records require explicit source attribution. Public satellite exploration is optional and does not imply automated satellite analysis."
      />
      <div className="flex flex-wrap gap-3">
        <Button
          variant={tab === "history" ? "default" : "outline"}
          onClick={() => setTab("history")}
        >
          {t("Historical events")}
        </Button>
        <Button
          variant={tab === "satellite" ? "default" : "outline"}
          onClick={() => setTab("satellite")}
        >
          {t("Satellite imagery")}
        </Button>
      </div>
      {tab === "satellite" && (
        <Card className="my-5 p-5">
          <h2 className="font-bold">Copernicus Sentinel-1 / Sentinel-2</h2>
          <p className="my-3 text-sm">
            Explore publicly available radar and optical imagery in Copernicus
            Browser. Cloud cover, acquisition dates and access terms affect
            availability. No imagery feed or landslide classifier is claimed.
          </p>
          <a
            href="https://browser.dataspace.copernicus.eu/"
            target="_blank"
            rel="noreferrer"
            className="text-blue-700 underline"
          >
            Open Copernicus Browser ↗
          </a>
        </Card>
      )}
      <RecordList
        key={tab}
        kind={tab}
        title={tab === "history" ? "Historical events" : "Satellite imagery"}
      />
      <h2 className="mb-4 mt-8 text-xl font-bold">
        {t("Public data sources")}
      </h2>
      <Load query={sources} />
      <div className="record-grid">
        {sources.data?.items.map((s: any) => (
          <Card className="p-5" key={s.name}>
            <a
              href={s.url}
              rel="noreferrer"
              target="_blank"
              className="font-bold text-blue-800 underline"
            >
              {s.name} ↗
            </a>
            <p className="mt-2 text-sm font-semibold">{s.purpose}</p>
            <p className="mt-2 text-sm text-slate-600">{s.access}</p>
            <p className="mt-2 text-xs text-slate-500">{s.license}</p>
          </Card>
        ))}
      </div>
    </>
  );
}

export function Analytics() {
  const query = useData("/api/analytics");
  return (
    <>
      <Heading
        title="Analytics"
        sub="Charts reflect stored records, including labelled sample data. Downloads retain source and simulation fields."
      />
      <Load query={query} />
      <div className="grid gap-5 lg:grid-cols-2">
        {[
          ["states", "Monitoring locations by state", "locations"],
          ["reports", "Report verification status", "reports"],
          ["history", "Imported historical events by month", "history"],
        ].map(([key, title, kind]) => (
          <Card className="min-w-0 p-5" key={key}>
            <h2 className="mb-3 font-bold">{title}</h2>
            <Export kind={kind} />
            <Chart data={query.data?.[key] || []} />
          </Card>
        ))}
      </div>
    </>
  );
}

export function Offline() {
  const { account, t, online } = useApp();
  const [rows, setRows] = useState<Queued[]>([]);
  const job = useAction();
  const refresh = async () => setRows(await queueList(account!.id));
  useEffect(() => {
    void refresh();
    const handler = () => {
      void refresh();
    };
    window.addEventListener("queue-changed", handler);
    return () => window.removeEventListener("queue-changed", handler);
  }, [account?.id]);
  return (
    <>
      <Heading
        title="Offline queue"
        sub="Reports and attachment files are retained in IndexedDB on this device, scoped to their author. Sync resumes after reconnecting and signing in with the same account."
      />
      <Card className="mb-5 p-5">
        <p className="mb-3 font-bold">
          {t(online ? "Online" : "Offline")} · {rows.length}{" "}
          {t("Pending uploads")}
        </p>
        <p className="mb-4 text-sm text-slate-600">
          Only pending submissions are stored offline. Submitted reports,
          warnings and map tiles require a connection. On a shared device,
          delete pending reports before handing it over.
        </p>
        <Button
          disabled={!online || job.busy}
          onClick={() =>
            job.run(async () => {
              const result = await syncQueue(account!.id);
              await refresh();
              if (!result.sent && rows.length)
                throw new Error("Another sync is in progress.");
            })
          }
        >
          {t("Sync now")}
        </Button>
        <Result job={job} />
      </Card>
      <div className="space-y-3">
        {rows.length === 0 && <Empty />}
        {rows.map((r) => (
          <Card className="p-5" key={r.key}>
            <b>
              {r.report.incident} · {r.report.location}
            </b>
            <p className="my-2 text-sm">{r.report.description}</p>
            <p className="text-xs">
              {r.files.length} files remaining ·{" "}
              {new Date(r.created).toLocaleString()}
            </p>
            {r.error && <p className="error mt-3">{r.error}</p>}
            <Button
              variant="danger"
              className="mt-3"
              onClick={() =>
                job.run(async () => {
                  if (queueIsSyncing())
                    throw new Error(
                      "Wait for the active sync to finish before deleting pending data.",
                    );
                  if (
                    window.confirm(
                      "Permanently delete this pending report and its local attachments?",
                    )
                  ) {
                    await queueDelete(r.key);
                    await refresh();
                  }
                }, "")
              }
            >
              {t("Delete")}
            </Button>
          </Card>
        ))}
      </div>
    </>
  );
}

export function Admin() {
  const { account, t } = useApp();
  const users = useData("/api/admin/users"),
    system = useData("/api/admin/system");
  const [kind, setKind] = useState("history"),
    [input, setInput] = useState(""),
    [result, setResult] = useState("");
  const job = useAction();
  return (
    <>
      <Heading
        title="Administration"
        sub="Assign portal roles, manage access, import attributed datasets and review the audit trail."
      />
      <Result job={job} />
      <Load query={users} />
      <Card className="overflow-auto">
        <table className="data-table">
          <thead>
            <tr>
              {["Name", "Email", "Role", "Status", "Action"].map((k) => (
                <th key={k}>{t(k)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {users.data?.items.map((u: Account & { active: boolean }) => (
              <tr key={u.id}>
                <td>{u.name}</td>
                <td>{u.email}</td>
                <td>
                  <Select
                    aria-label={"Role for " + u.email}
                    disabled={u.id === account?.id || job.busy}
                    value={u.role}
                    onChange={(e) =>
                      job.run(async () => {
                        await patch("/api/admin/users/" + u.id, {
                          role: e.target.value,
                        });
                        await users.refresh();
                        await system.refresh();
                      })
                    }
                  >
                    {["citizen", "official", "admin"].map((r) => (
                      <option key={r} value={r}>
                        {t(
                          r === "admin"
                            ? "Administrator"
                            : r === "official"
                              ? "Field official"
                              : "Citizen",
                        )}
                      </option>
                    ))}
                  </Select>
                </td>
                <td>{t(u.active ? "Active" : "Inactive")}</td>
                <td>
                  <Button
                    disabled={u.id === account?.id || job.busy}
                    variant="outline"
                    onClick={() =>
                      job.run(async () => {
                        await patch("/api/admin/users/" + u.id, {
                          active: !u.active,
                        });
                        await users.refresh();
                        await system.refresh();
                      })
                    }
                  >
                    {u.active ? "Deactivate" : "Activate"}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Card className="my-5 p-5">
        <h2 className="mb-3 font-bold">{t("Import data")}</h2>
        <p className="mb-3 text-sm text-slate-600">
          JSON {`{items:[...]}`} or point GeoJSON FeatureCollection, up to 500
          records per batch. Every record needs source and simulated
          (true/false). Repeating identical records is idempotent. Real
          population records also require year, resolutionM and license.
        </p>
        <a
          className="text-sm text-blue-700 underline"
          href="/sample-import.json"
          download
        >
          Download sample import format
        </a>
        <form
          className="mt-4 space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            void job.run(async () => {
              const result = await post(
                "/api/admin/import/" + kind,
                JSON.parse(input),
              );
              setResult(
                `${result.inserted} imported; ${result.unchanged} unchanged`,
              );
              await system.refresh();
            });
          }}
        >
          <Select
            aria-label="Import collection"
            value={kind}
            onChange={(e) => setKind(e.target.value)}
          >
            {[
              "history",
              "locations",
              "roads",
              "villages",
              "infrastructure",
              "satellite",
            ].map((v) => (
              <option key={v}>{v}</option>
            ))}
          </Select>
          <Field label="JSON / GeoJSON">
            <textarea
              required
              value={input}
              onChange={(e) => setInput(e.target.value)}
              className="min-h-48 font-mono text-xs"
            />
          </Field>
          <Button disabled={job.busy} type="submit">
            {t("Import data")}
          </Button>
        </form>
        {result && <p className="success mt-3">{result}</p>}
      </Card>
      <Load query={system} />
      <Card className="overflow-auto p-5">
        <h2 className="mb-4 font-bold">System / audit</h2>
        <p className="text-sm">
          Database: {system.data?.health.database} · PostGIS{" "}
          {system.data?.health.postgis}
        </p>
        <p className="my-2 text-sm">{system.data?.notificationMode}</p>
        <table className="data-table">
          <thead>
            <tr>
              <th>Time</th>
              <th>Action</th>
              <th>Actor</th>
              <th>Target</th>
            </tr>
          </thead>
          <tbody>
            {system.data?.audit.map((a: any, i: number) => (
              <tr key={i}>
                <td>{time(a.at)}</td>
                <td>{a.action}</td>
                <td>{a.actor || "Local management"}</td>
                <td>{a.target}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </>
  );
}

export function Settings() {
  const { account, setAccount, lang, setLang, t } = useApp();
  const [inApp, setInApp] = useState(account?.preferences.inApp ?? true),
    [states, setStates] = useState(
      (account?.preferences.states || []).join(","),
    );
  const job = useAction();
  return (
    <>
      <Heading title="Settings" />
      <Card className="max-w-2xl p-5">
        <p className="mb-5 font-bold">
          {account?.name} · {account?.email}
        </p>
        <form
          className="space-y-4"
          onSubmit={(e) => {
            e.preventDefault();
            void job.run(async () => {
              setAccount(
                await patch("/api/settings", {
                  language: lang,
                  inApp,
                  states: states
                    .split(",")
                    .map((v) => v.trim())
                    .filter(Boolean),
                }),
              );
            });
          }}
        >
          <Field label="Language">
            <Select value={lang} onChange={(e) => setLang(e.target.value)}>
              <option value="en">English</option>
              <option value="hi">हिन्दी</option>
              <option value="as">অসমীয়া</option>
            </Select>
          </Field>
          <label className="flex gap-2 text-sm">
            <input
              type="checkbox"
              checked={inApp}
              onChange={(e) => setInApp(e.target.checked)}
            />
            {t("In-app notifications")}
          </label>
          <Field label="States for notifications (comma-separated; empty means all)">
            <Input value={states} onChange={(e) => setStates(e.target.value)} />
          </Field>
          <Button type="submit" disabled={job.busy}>
            {t("Save")}
          </Button>
        </form>
        <Result job={job} />
        <p className="mt-5 text-sm text-slate-600">
          The core portal interface supports English, Hindi and Assamese. User
          reports, dataset attribution and source documents retain their
          original language. In-app notifications are delivered when an official
          publishes an alert. No paid SMS service is required.
        </p>
      </Card>
    </>
  );
}
