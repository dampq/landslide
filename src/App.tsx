import RequestError from "./components/RequestError";
import { createContext, useContext, useEffect, useState } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  NavLink,
  Outlet,
  useNavigate,
} from "react-router-dom";
import { ShieldAlert, Menu, LogOut, CloudOff, Languages } from "lucide-react";
import { api, Account, useOnline, syncQueue, flushPendingLogout } from "./lib";
import { languages, translate, type TranslationParams } from "./i18n";
import { Button, Input, Card } from "./components/ui";
import {
  Dashboard,
  Reports,
  Monitoring,
  MapPage,
  Weather,
  Prediction,
  Alerts,
  ResponsePage,
  History,
  Analytics,
  Offline,
  Admin,
  Settings,
} from "./Portal";

type Context = {
  account: Account | null;
  setAccount: (a: Account | null) => void;
  lang: string;
  setLang: (v: string) => void;
  t: (key: string, params?: TranslationParams) => string;
  online: boolean;
};
const AppContext = createContext<Context>(null!);
export const useApp = () => useContext(AppContext);
const routes = [
  ["Dashboard", "/"],
  ["GIS map", "/map"],
  ["Reports", "/reports"],
  ["Monitoring", "/monitoring"],
  ["Weather", "/weather"],
  ["Model integration", "/prediction"],
  ["Alerts", "/alerts"],
  ["Response", "/response"],
  ["History & imagery", "/history"],
  ["Analytics", "/analytics"],
  ["Offline queue", "/offline"],
  ["Administration", "/admin"],
  ["Settings", "/settings"],
];
function Shell() {
  const { account, setAccount, lang, setLang, t, online } = useApp();
  const [mobile, setMobile] = useState(false);
  const nav = useNavigate();
  if (!account) return <Navigate to="/login" replace />;
  const allowed = routes.filter(
    ([_, path]) =>
      !(
        account.role === "citizen" &&
        ["/response", "/analytics", "/prediction"].includes(path)
      ) &&
      (path !== "/admin" || account.role === "admin"),
  );
  return (
    <div className="min-h-screen bg-slate-50">
      <header className="portal-header">
        <button
          aria-label={t("Menu")}
          className="md:hidden"
          onClick={() => setMobile(!mobile)}
        >
          <Menu />
        </button>
        <ShieldAlert className="text-orange-300" />
        <div>
          <b className="tracking-wide">{t("ASHTARAKSHA")}</b>
          <div className="text-xs text-slate-300">
            {t("North East India · Landslide monitoring")}{" "}
          </div>
        </div>
        <span className="ml-auto flex items-center gap-2 text-xs">
          {!online && <CloudOff size={16} />}
          <span>{t(online ? "Online" : "Offline")}</span>
        </span>
        <Languages size={18} />
        <select
          aria-label={t("Language")}
          className="rounded border border-slate-500 bg-slate-800 p-1 text-sm"
          value={lang}
          onChange={(e) => setLang(e.target.value)}
        >
          {Object.entries(languages).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <button
          aria-label={t("Sign out")}
          title={t("Sign out")}
          onClick={async () => {
            if (online) {
              try {
                await api("/api/auth/logout", { method: "POST" });
              } catch {
                localStorage.setItem("ashtaraksha-logout-pending", "true");
              }
            } else localStorage.setItem("ashtaraksha-logout-pending", "true");
            localStorage.removeItem("ashtaraksha-account");
            setAccount(null);
            nav("/login");
          }}
        >
          <LogOut size={20} />
        </button>
      </header>
      <div className="flex">
        <aside
          className={`${mobile ? "block" : "hidden"} portal-sidebar md:block`}
        >
          <div className="mb-4 rounded-xl bg-slate-100 p-3 text-sm">
            <b>{account.name}</b>
            <div className="text-xs text-slate-500">
              {t(
                account.role === "admin"
                  ? "Administrator"
                  : account.role === "official"
                    ? "Field official"
                    : "Citizen",
              )}
            </div>
          </div>
          <nav aria-label={t("Main navigation")}>
            {allowed.map(([label, path]) => (
              <NavLink
                end={path === "/"}
                key={path}
                to={path}
                onClick={() => setMobile(false)}
                className={({ isActive }) =>
                  `mb-1 block rounded-xl px-3 py-2.5 text-sm font-semibold ${isActive ? "bg-blue-100 text-blue-900" : "text-slate-600 hover:bg-slate-100"}`
                }
              >
                {t(label)}
              </NavLink>
            ))}
          </nav>
        </aside>
        <main className="min-w-0 flex-1 p-3 md:p-7">
          <div
            className="mb-5 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950"
            role="note"
          >
            {t("Sample data notice")}
          </div>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
async function authRequest<T = Account>(
  path: string,
  body?: Record<string, string>,
): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    return await api<T>(path, {
      method: body ? "POST" : "GET",
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
  } catch (error) {
    if (controller.signal.aborted)
      throw new Error(
        "The sign-in service is taking too long. Please try again.",
      );
    throw error;
  } finally {
    clearTimeout(timer);
  }
}
function Auth() {
  const { setAccount, t, lang, setLang } = useApp();
  const [register, setRegister] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [invalidField, setInvalidField] = useState(""),
    [busy, setBusy] = useState(false);
  const nav = useNavigate();
  function showError(message: string, form: HTMLFormElement, field = "") {
    setError(message);
    setInvalidField(field);
    const input = form.elements.namedItem(field);
    if (input instanceof HTMLElement) input.focus();
    requestAnimationFrame(() =>
      document
        .getElementById("auth-error")
        ?.scrollIntoView({ block: "nearest" }),
    );
  }
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy) return;
    const form = e.currentTarget;
    const fields = new FormData(form);
    const email = String(fields.get("email") || "")
      .trim()
      .toLowerCase();
    const password = String(fields.get("password") || "");
    const name = String(fields.get("name") || "").trim();
    setError("");
    setNotice("");
    setInvalidField("");
    if (register && !name) return showError("Enter your name.", form, "name");
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || email.length > 254)
      return showError("Enter a valid email address.", form, "email");
    if (!password) return showError("Enter your password.", form, "password");
    if (register && password.length < 12)
      return showError(
        "Use at least 12 characters for a new account password.",
        form,
        "password",
      );
    if (password.length > 128)
      return showError(
        "Password must contain no more than 128 characters.",
        form,
        "password",
      );
    setBusy(true);
    try {
      await flushPendingLogout();
      if (register) {
        await authRequest("/api/auth/register", { email, password, name });
        setNotice(
          "Your account was created. Sign in with your email and password if automatic sign-in does not finish.",
        );
        setRegister(false);
      }
      const account = await authRequest("/api/auth/login", { email, password });
      // Do not report success if third-party/embedded-browser settings blocked the cookie.
      let session: Account;
      try {
        session = await authRequest("/api/auth/me");
      } catch (error) {
        if ((error as Error & { status?: number }).status === 401)
          throw new Error(
            "Your browser did not retain the sign-in session. Open this website in a normal browser tab and allow cookies for this site.",
          );
        throw error;
      }
      if (session.id !== account.id)
        throw new Error("The sign-in session changed. Please try again.");
      setAccount(session);
      nav("/");
    } catch (error) {
      const issue = error as Error & { status?: number };
      const message =
        issue.status && issue.status >= 500
          ? "Sign-in is temporarily unavailable. Please retry shortly."
          : issue.name === "AbortError"
            ? "The sign-in service is taking too long. Please try again."
            : issue.message === "Failed to fetch"
              ? "Cannot connect to the sign-in service. Check your connection and try again."
              : issue.message;
      showError(message, form);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="min-h-screen bg-[#0d2038] p-5 text-white">
      <header className="mx-auto flex max-w-6xl items-center gap-3 py-4">
        <ShieldAlert className="text-orange-300" />
        <b>{t("ASHTARAKSHA")}</b>
        <select
          aria-label={t("Language")}
          className="ml-auto rounded bg-slate-700 p-2"
          value={lang}
          onChange={(e) => setLang(e.target.value)}
        >
          {Object.entries(languages).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
      </header>
      <div className="mx-auto grid max-w-6xl items-center gap-10 py-12 lg:grid-cols-2">
        <section>
          <div className="mb-5 text-sm font-bold tracking-widest text-orange-300">
            {t("NORTH EAST INDIA")}{" "}
          </div>
          <h1 className="text-4xl font-black leading-tight md:text-6xl">
            {t("Observe. Report.")} <br />
            {t("Prepare together.")}{" "}
          </h1>
          <p className="mt-6 max-w-lg text-lg text-slate-300">
            {t(
              "A community platform for landslide monitoring, field verification and coordinated response.",
            )}{" "}
          </p>
          <div className="mt-8 rounded-xl border border-white/20 p-5 text-sm text-slate-200">
            {t("Sample data notice")}
          </div>
          <p className="mt-6 text-sm text-slate-300">
            {t("Remember to stay safe")}
          </p>
        </section>
        <Card className="p-7 text-slate-900">
          <h2 className="mb-5 text-2xl font-black">
            {t(register ? "Create account" : "Sign in")}
          </h2>
          {notice && (
            <div className="success mb-4" role="status">
              {t(notice)}
            </div>
          )}
          <form className="space-y-4" onSubmit={submit} noValidate>
            {error && (
              <div id="auth-error" className="error" role="alert">
                <RequestError message={error} />
              </div>
            )}
            {register && (
              <label className="field">
                {t("Name")}
                <Input
                  name="name"
                  required
                  maxLength={100}
                  autoComplete="name"
                  aria-invalid={invalidField === "name" || undefined}
                  aria-describedby={
                    invalidField === "name" ? "auth-error" : undefined
                  }
                />
              </label>
            )}
            <label className="field">
              {t("Email")}
              <Input
                name="email"
                type="email"
                required
                autoComplete="email"
                aria-invalid={invalidField === "email" || undefined}
                aria-describedby={
                  invalidField === "email" ? "auth-error" : undefined
                }
              />
            </label>
            <label className="field">
              {t("Password")}
              <Input
                aria-label={t("Password")}
                name="password"
                type="password"
                required
                minLength={register ? 12 : undefined}
                maxLength={128}
                aria-invalid={invalidField === "password" || undefined}
                aria-describedby={
                  invalidField === "password" ? "auth-error" : "password-help"
                }
                autoComplete={register ? "new-password" : "current-password"}
              />
              <small id="password-help">
                {t(
                  register
                    ? "Minimum 12 characters"
                    : "Enter the password for your registered account.",
                )}
              </small>
            </label>
            <Button type="submit" disabled={busy} className="w-full">
              {busy ? t("Loading…") : t(register ? "Register" : "Sign in")}
            </Button>
          </form>
          <Button
            variant="ghost"
            disabled={busy}
            className="mt-4 w-full"
            onClick={() => {
              setRegister(!register);
              setError("");
              setNotice("");
              setInvalidField("");
            }}
          >
            {t(register ? "Back to sign in" : "Create account")}
          </Button>
          <p className="mt-4 text-xs text-slate-500">
            {t(
              "Registration creates a citizen account. Official and administrator roles are assigned by an administrator.",
            )}{" "}
          </p>
        </Card>
      </div>
    </div>
  );
}
function Restricted({
  children,
  admin = false,
}: {
  children: React.ReactNode;
  admin?: boolean;
}) {
  const { account } = useApp();
  return account &&
    (admin ? account.role === "admin" : account.role !== "citizen") ? (
    <>{children}</>
  ) : (
    <Navigate to="/" replace />
  );
}
export default function App() {
  const [account, setAccountState] = useState<Account | null>(null),
    [ready, setReady] = useState(false),
    [lang, setLangState] = useState(
      localStorage.getItem("ashtaraksha-language") || "en",
    );
  const online = useOnline();
  const setAccount = (a: Account | null) => {
    setAccountState(a);
    if (
      a?.preferences.language &&
      !localStorage.getItem("ashtaraksha-language")
    ) {
      setLangState(a.preferences.language);
      localStorage.setItem("ashtaraksha-language", a.preferences.language);
    }
    if (a) localStorage.setItem("ashtaraksha-account", JSON.stringify(a));
    else localStorage.removeItem("ashtaraksha-account");
  };
  const setLang = (v: string) => {
    setLangState(v);
    localStorage.setItem("ashtaraksha-language", v);
    document.documentElement.lang = v;
  };
  useEffect(() => {
    (localStorage.getItem("ashtaraksha-logout-pending")
      ? Promise.reject(new Error("Signed out locally"))
      : api<Account>("/api/auth/me")
    )
      .then(setAccount)
      .catch(() => {
        if (
          !navigator.onLine &&
          !localStorage.getItem("ashtaraksha-logout-pending")
        ) {
          try {
            setAccountState(
              JSON.parse(localStorage.getItem("ashtaraksha-account") || "null"),
            );
          } catch {}
        }
      })
      .finally(() => setReady(true));
    const expired = () => setAccount(null);
    window.addEventListener("session-expired", expired);
    return () => window.removeEventListener("session-expired", expired);
  }, []);
  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);
  useEffect(() => {
    if (online && localStorage.getItem("ashtaraksha-logout-pending")) {
      void flushPendingLogout().catch(() => {});
      return;
    }
    if (online && account) {
      void syncQueue(account.id).catch(() => {});
    }
  }, [online, account?.id]);
  if (!ready) return <p className="p-10">{translate(lang, "Loading…")}</p>;
  return (
    <AppContext.Provider
      value={{
        account,
        setAccount,
        lang,
        setLang,
        t: (key, params) => translate(lang, key, params),
        online,
      }}
    >
      <BrowserRouter>
        <Routes>
          <Route
            path="/login"
            element={account ? <Navigate to="/" /> : <Auth />}
          />
          <Route element={<Shell />}>
            <Route index element={<Dashboard />} />
            <Route path="map" element={<MapPage />} />
            <Route path="reports" element={<Reports />} />
            <Route path="monitoring" element={<Monitoring />} />
            <Route path="weather" element={<Weather />} />
            <Route
              path="prediction"
              element={
                <Restricted>
                  <Prediction />
                </Restricted>
              }
            />
            <Route path="alerts" element={<Alerts />} />
            <Route
              path="response"
              element={
                <Restricted>
                  <ResponsePage />
                </Restricted>
              }
            />
            <Route path="history" element={<History />} />
            <Route
              path="analytics"
              element={
                <Restricted>
                  <Analytics />
                </Restricted>
              }
            />
            <Route path="offline" element={<Offline />} />
            <Route
              path="admin"
              element={
                <Restricted admin>
                  <Admin />
                </Restricted>
              }
            />
            <Route path="settings" element={<Settings />} />
            <Route path="roads" element={<Navigate to="/monitoring" />} />
            <Route path="villages" element={<Navigate to="/monitoring" />} />
            <Route path="sensors" element={<Navigate to="/monitoring" />} />
          </Route>
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </BrowserRouter>
    </AppContext.Provider>
  );
}
