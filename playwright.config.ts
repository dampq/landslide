import { defineConfig } from "@playwright/test";
const DATABASE_URL =
  "postgresql+psycopg://ashtaraksha:local-development@127.0.0.1:5433/ashtaraksha_e2e_test";
export default defineConfig({
  testDir: "tests/browser",
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  expect: { timeout: 10000 },
  use: {
    baseURL: "http://127.0.0.1:4173",
    headless: true,
    launchOptions: {
      executablePath: process.env.CHROMIUM_PATH || "/usr/bin/chromium",
      args: ["--no-sandbox", "--disable-dev-shm-usage"],
    },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command:
        "backend/.venv/bin/python scripts/prepare-e2e.py && cd backend && .venv/bin/python -m uvicorn api.main:app --port 8000",
      url: "http://127.0.0.1:8000/health",
      env: { DATABASE_URL },
      reuseExistingServer: false,
      timeout: 60000,
    },
    {
      command: "npm run preview -- --host 127.0.0.1 --port 4173 --strictPort",
      url: "http://127.0.0.1:4173",
      reuseExistingServer: false,
      timeout: 60000,
    },
  ],
});
