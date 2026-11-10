import { locale } from "./i18n";
import { useCallback, useEffect, useState, useRef } from "react";
export type Account = {
  id: string;
  email: string;
  name: string;
  role: "citizen" | "official" | "admin";
  preferences: { language?: string; inApp?: boolean; states?: string[] };
};
export type Row = {
  id: string;
  kind: string;
  name?: string;
  lat?: number;
  lng?: number;
  source?: string;
  simulated?: boolean;
  updatedAt: number;
  createdAt: number;
  [key: string]: any;
};
export async function api<T = any>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const response = await fetch(path, {
    ...options,
    headers,
    credentials: "same-origin",
  });
  if (!response.ok) {
    let detail;
    try {
      detail = (await response.json()).detail;
    } catch {
      detail = response.statusText;
    }
    if (response.status === 401 && !path.startsWith("/api/auth/"))
      window.dispatchEvent(new Event("session-expired"));
    const error = new Error(
      Array.isArray(detail)
        ? "Some fields are invalid. Check the form and try again."
        : typeof detail === "string"
          ? detail
          : "Some fields are invalid. Check the form and try again.",
    ) as Error & { status: number };
    error.status = response.status;
    throw error;
  }
  return response.json();
}
export const post = (path: string, body: any = {}) =>
  api(path, { method: "POST", body: JSON.stringify(body) });
export const patch = (path: string, body: any) =>
  api(path, { method: "PATCH", body: JSON.stringify(body) });
export function useData<T = any>(path: string) {
  const [data, setData] = useState<T | null>(null),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  const generation = useRef(0);
  const refresh = useCallback(async () => {
    const requestId = ++generation.current;
    setLoading(true);
    setError("");
    try {
      const result = await api<T>(path);
      if (requestId === generation.current) setData(result);
    } catch (e) {
      if (requestId === generation.current) setError((e as Error).message);
    } finally {
      if (requestId === generation.current) setLoading(false);
    }
  }, [path]);
  useEffect(() => {
    setData(null);
    void refresh();
    return () => {
      generation.current++;
    };
  }, [refresh]);
  return { data, error, loading, refresh };
}
export function useOnline() {
  const [online, setOnline] = useState(navigator.onLine);
  useEffect(() => {
    const update = () => setOnline(navigator.onLine);
    window.addEventListener("online", update);
    window.addEventListener("offline", update);
    return () => {
      window.removeEventListener("online", update);
      window.removeEventListener("offline", update);
    };
  }, []);
  return online;
}
export function time(value: number) {
  return new Date(value * 1000).toLocaleString(
    locale(document.documentElement.lang),
  );
}
export type Queued = {
  key: string;
  userId: string;
  report: any;
  files: File[];
  created: number;
  error?: string;
  serverId?: string;
};
function openQueue(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open("ashtaraksha-offline", 1);
    request.onupgradeneeded = () =>
      request.result.createObjectStore("reports", { keyPath: "key" });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}
async function transaction(
  mode: IDBTransactionMode,
  work: (store: IDBObjectStore) => IDBRequest,
): Promise<any> {
  const db = await openQueue();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("reports", mode);
    const req = work(tx.objectStore("reports"));
    let result: any;
    req.onsuccess = () => {
      result = req.result;
    };
    tx.oncomplete = () => {
      db.close();
      if (mode === "readwrite")
        window.dispatchEvent(new Event("queue-changed"));
      resolve(result);
    };
    tx.onerror = () => {
      db.close();
      reject(tx.error);
    };
  });
}
export async function queueList(userId: string): Promise<Queued[]> {
  return (await transaction("readonly", (s) => s.getAll())).filter(
    (r: Queued) => r.userId === userId,
  );
}
export const queuePut = (row: Queued) =>
  transaction("readwrite", (s) => s.put(row));
export const queueDelete = (key: string) =>
  transaction("readwrite", (s) => s.delete(key));
let syncTask: Promise<{ sent: number }> | null = null;
export function queueIsSyncing() {
  return syncTask !== null;
}
export async function syncQueue(userId: string): Promise<{ sent: number }> {
  if (syncTask) {
    await syncTask;
    return syncQueue(userId);
  }
  const task = (async () => {
    let sent = 0;
    const current = await api<Account>("/api/auth/me");
    if (current.id !== userId)
      throw new Error("Sign in with the account that created these reports.");
    for (const row of await queueList(userId)) {
      try {
        const saved = await post("/api/reports", row.report);
        row.serverId = saved.id;
        await queuePut(row);
        while (row.files.length) {
          const body = new FormData();
          body.append("file", row.files[0]);
          await api(`/api/reports/${saved.id}/media`, { method: "POST", body });
          row.files.shift();
          await queuePut(row);
        }
        await queueDelete(row.key);
        sent++;
      } catch (e) {
        row.error = (e as Error).message;
        await queuePut(row);
        throw e;
      }
    }
    return { sent };
  })();
  syncTask = task;
  window.dispatchEvent(new Event("queue-changed"));
  try {
    return await task;
  } finally {
    syncTask = null;
    window.dispatchEvent(new Event("queue-changed"));
  }
}

let pendingLogout: Promise<void> | null = null;
export async function flushPendingLogout() {
  if (!localStorage.getItem("ashtaraksha-logout-pending")) return;
  if (pendingLogout) return pendingLogout;
  pendingLogout = (async () => {
    try {
      await api("/api/auth/logout", { method: "POST" });
    } catch (e) {
      if ((e as Error & { status?: number }).status !== 401) throw e;
    }
    localStorage.removeItem("ashtaraksha-logout-pending");
  })();
  try {
    await pendingLogout;
  } finally {
    pendingLogout = null;
  }
}
