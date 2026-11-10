import { spawn } from "node:child_process";
import { resolve } from "node:path";
import { existsSync } from "node:fs";
const root = process.cwd();
const python = resolve(
  root,
  "backend",
  ".venv",
  process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
);
if (!existsSync(python)) {
  console.error(
    "Install backend requirements into backend/.venv first; see README.md.",
  );
  process.exit(1);
}
const children = [
  spawn(
    process.platform === "win32" ? "npm.cmd" : "npm",
    ["run", "dev", "--", "--host", "127.0.0.1", "--strictPort"],
    { cwd: root, stdio: "inherit" },
  ),
  spawn(
    python,
    ["-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8000"],
    { cwd: resolve(root, "backend"), stdio: "inherit" },
  ),
];
let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) child.kill("SIGTERM");
  setTimeout(() => process.exit(code), 500).unref();
}
for (const child of children) {
  child.on("error", (e) => {
    console.error(e.message);
    stop(1);
  });
  child.on("exit", (code) => {
    if (!stopping) stop(code ?? 1);
  });
}
process.on("SIGINT", () => stop());
process.on("SIGTERM", () => stop());
