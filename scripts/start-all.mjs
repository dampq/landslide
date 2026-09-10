import { existsSync } from "node:fs";
import { spawn } from "node:child_process";
import { resolve } from "node:path";

const root = process.cwd();
const backend = resolve(root, "backend", "RayaproluSamiksha-ashtaraksha-backend-f48cca4");
const backendPython = process.platform === "win32"
  ? resolve(backend, ".venv", "Scripts", "python.exe")
  : resolve(backend, ".venv", "bin", "python");
const pythonCommand = existsSync(backendPython) ? backendPython : "python";

if (!existsSync(backend)) {
  console.error(`Backend folder not found: ${backend}`);
  console.error("Extract ashtaraksha-backend.zip into the backend folder first.");
  process.exit(1);
}

const processes = [
  spawn(process.platform === "win32" ? "npm.cmd" : "npm", ["run", "dev", "--", "--host", "127.0.0.1"], {
    cwd: root,
    stdio: "inherit",
    shell: process.platform === "win32",
  }),
  spawn(pythonCommand, ["run.py"], {
    cwd: backend,
    stdio: "inherit",
  }),
];

const stop = () => {
  for (const child of processes) {
    if (!child.killed) child.kill();
  }
};

process.on("SIGINT", () => {
  stop();
  process.exit(0);
});
process.on("SIGTERM", stop);

for (const child of processes) {
  child.on("exit", (code) => {
    if (code && code !== 0) {
      stop();
      process.exit(code);
    }
  });
}