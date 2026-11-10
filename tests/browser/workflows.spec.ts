import { test, expect, Page } from "@playwright/test";
async function login(page: Page, role: string) {
  await page.goto("/login");
  await page.getByLabel("Email", { exact: true }).fill(`${role}@e2e.test`);
  await page
    .getByLabel("Password", { exact: true })
    .fill("e2e-test-password-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Dashboard", exact: true }),
  ).toBeVisible();
}

test("citizen submits GPS and image; official verifies; admin audit records the action", async ({
  browser,
}) => {
  const citizen = await browser.newContext({
    geolocation: { latitude: 25.297, longitude: 91.582 },
    permissions: ["geolocation"],
  });
  const cp = await citizen.newPage();
  await login(cp, "citizen");
  await expect(
    cp.getByRole("link", { name: "Administration", exact: true }),
  ).toHaveCount(0);
  await cp.getByRole("link", { name: "Reports", exact: true }).click();
  await cp
    .getByLabel("Location", { exact: true })
    .fill("Browser integration incident");
  await cp.getByRole("button", { name: "Use my GPS" }).click();
  await expect(cp.getByLabel("Latitude", { exact: true })).toHaveValue(
    "25.297000",
  );
  await cp
    .getByLabel("Description", { exact: true })
    .fill(
      "A safe demonstration incident submitted during browser integration testing.",
    );
  await cp
    .getByLabel("Photographs / videos", { exact: true })
    .setInputFiles("tests/fixtures/field-sample.png");
  await cp.getByLabel("Confirm observations").check();
  await cp.getByRole("button", { name: "Submit report", exact: true }).click();
  await expect(
    cp.getByRole("status").filter({ hasText: "Report sent" }),
  ).toBeVisible();
  const card = cp
    .locator(".rounded-2xl")
    .filter({
      has: cp.getByText("Ground Crack · Browser integration incident", {
        exact: true,
      }),
    })
    .last();
  // The default selected incident is Ground Crack.
  await expect(
    cp.getByText("Ground Crack · Browser integration incident", {
      exact: true,
    }),
  ).toBeVisible();
  await card
    .getByRole("button", { name: "Photographs / videos", exact: true })
    .click();
  await expect(cp.getByText(/OpenCV: 60 × 40/)).toBeVisible();
  const official = await browser.newContext();
  const op = await official.newPage();
  await login(op, "official");
  await op.getByRole("link", { name: "Reports", exact: true }).click();
  const report = op
    .locator(".rounded-2xl")
    .filter({
      has: op.getByText("Ground Crack · Browser integration incident", {
        exact: true,
      }),
    })
    .last();
  await report
    .getByLabel("Review note")
    .fill("Confirmed as a synthetic browser test.");
  await report.getByRole("button", { name: "Verify", exact: true }).click();
  await expect(report.getByText("Verified", { exact: true })).toBeVisible();
  await cp.reload();
  await expect(cp.getByText("Verified", { exact: true })).toBeVisible();
  const admin = await browser.newContext();
  const ap = await admin.newPage();
  await login(ap, "admin");
  await ap.getByRole("link", { name: "Administration", exact: true }).click();
  await expect(ap.getByText("report:Verified", { exact: true })).toBeVisible();
  await citizen.close();
  await official.close();
  await admin.close();
});

test("offline app shell preserves queued report and image through reload, then synchronises once", async ({
  browser,
}) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  await login(page, "citizen");
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
  await page.reload();
  await page.waitForFunction(() => !!navigator.serviceWorker.controller);
  await context.setOffline(true);
  await page.goto("/reports");
  await expect(
    page.getByRole("heading", { name: "Reports", exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Location", { exact: true })
    .fill("Offline browser incident");
  await page.getByLabel("Latitude", { exact: true }).fill("25.297");
  await page.getByLabel("Longitude", { exact: true }).fill("91.582");
  await page
    .getByLabel("Description", { exact: true })
    .fill(
      "An offline incident with an actual attachment for reconnect testing.",
    );
  await page
    .getByLabel("Photographs / videos", { exact: true })
    .setInputFiles("tests/fixtures/field-sample.png");
  await page.getByLabel("Confirm observations").check();
  await page
    .getByRole("button", { name: "Submit report", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Report saved to this device" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Offline queue", exact: true }).click();
  await page.reload();
  await expect(
    page.getByText("Ground Crack · Offline browser incident", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/1 files remaining/)).toBeVisible();
  await context.setOffline(false);
  await expect(
    page.getByText("Ground Crack · Offline browser incident", { exact: true }),
  ).toHaveCount(0, { timeout: 15000 });
  await page.getByRole("link", { name: "Reports", exact: true }).click();
  await expect(
    page.getByText("Ground Crack · Offline browser incident", { exact: true }),
  ).toHaveCount(1);
  const report = page
    .locator(".rounded-2xl")
    .filter({
      has: page.getByText("Ground Crack · Offline browser incident", {
        exact: true,
      }),
    })
    .last();
  await report
    .getByRole("button", { name: "Photographs / videos", exact: true })
    .click();
  await expect(report.getByText(/OpenCV: 60 × 40/)).toBeVisible();
  await context.close();
});

test("official sensor simulation, weather sample, spatial layers and warning publication", async ({
  page,
}) => {
  await login(page, "official");
  await page.getByRole("link", { name: "Monitoring", exact: true }).click();
  await page.getByRole("button", { name: "Sensors", exact: true }).click();
  await page.getByRole("button", { name: "Run sensor simulation" }).click();
  await expect(page.getByText("Simulated", { exact: true })).toHaveCount(8);
  await page.getByRole("link", { name: "Weather", exact: true }).click();
  await page
    .getByLabel("Location", { exact: true })
    .selectOption("demo-location-0");
  await expect(
    page.getByText("Synthetic weather demonstration; not Open-Meteo data", {
      exact: false,
    }),
  ).toBeVisible();
  await page.getByRole("link", { name: "GIS map", exact: true }).click();
  await expect(page.locator(".leaflet-interactive")).toHaveCount(48);
  await page.getByLabel("history", { exact: true }).uncheck();
  await expect(page.locator(".leaflet-interactive")).toHaveCount(40);
  await page.getByRole("link", { name: "Alerts", exact: true }).click();
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await page.getByLabel("Name", { exact: true }).fill("Browser test warning");
  await page
    .getByLabel("Description", { exact: true })
    .fill("Synthetic browser test warning; no actual event.");
  await page
    .getByLabel("Action", { exact: true })
    .fill("Review the demonstration only.");
  await page
    .getByLabel("Location", { exact: true })
    .selectOption("demo-location-0");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(page.getByText("Draft", { exact: true })).toBeVisible();
  await page
    .getByLabel("Review note", { exact: true })
    .fill("Reviewed as a synthetic test warning.");
  await page.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(page.getByText("Approved", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Publish", exact: true }).click();
  await expect(page.getByText("Published", { exact: true })).toBeVisible();
});

test("mobile layout, Hindi and Assamese navigation, model unavailable state", async ({
  browser,
}) => {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
  });
  const page = await context.newPage();
  await login(page, "official");
  await expect(
    page.getByRole("button", { name: "Menu", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Language", { exact: true }).selectOption("hi");
  await expect(
    page.getByRole("heading", { name: "डैशबोर्ड", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Menu", exact: true }).click();
  await page.getByRole("link", { name: "मॉडल एकीकरण", exact: true }).click();
  await expect(
    page.getByText("मॉडल उपलब्ध नहीं है", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("Language", { exact: true }).selectOption("as");
  await expect(
    page.getByRole("heading", { name: "মডেল সংযোগ", exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "test-results/mobile-assamese.png",
    fullPage: true,
  });
  await context.close();
});

test("interrupted media upload stays queued and retries without duplicating the report", async ({
  page,
}) => {
  await login(page, "citizen");
  await page.route("**/api/reports/*/media", (route) =>
    route.request().method() === "POST"
      ? route.abort("failed")
      : route.continue(),
  );
  await page.getByRole("link", { name: "Reports", exact: true }).click();
  await page
    .getByLabel("Location", { exact: true })
    .fill("Interrupted upload incident");
  await page.getByLabel("Latitude", { exact: true }).fill("25.297");
  await page.getByLabel("Longitude", { exact: true }).fill("91.582");
  await page
    .getByLabel("Description", { exact: true })
    .fill("Testing an interrupted image upload after the report was stored.");
  await page
    .getByLabel("Photographs / videos", { exact: true })
    .setInputFiles("tests/fixtures/field-sample.png");
  await page.getByLabel("Confirm observations").check();
  await page
    .getByRole("button", { name: "Submit report", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Report saved to this device" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Offline queue", exact: true }).click();
  await expect(
    page.getByText("Ground Crack · Interrupted upload incident", {
      exact: true,
    }),
  ).toBeVisible();
  await page.unroute("**/api/reports/*/media");
  await page.getByRole("button", { name: "Sync now", exact: true }).click();
  await expect(
    page.getByText("Ground Crack · Interrupted upload incident", {
      exact: true,
    }),
  ).toHaveCount(0);
  await page.getByRole("link", { name: "Reports", exact: true }).click();
  await expect(
    page.getByText("Ground Crack · Interrupted upload incident", {
      exact: true,
    }),
  ).toHaveCount(1);
  const card = page
    .locator(".rounded-2xl")
    .filter({
      has: page.getByText("Ground Crack · Interrupted upload incident", {
        exact: true,
      }),
    })
    .last();
  await card
    .getByRole("button", { name: "Photographs / videos", exact: true })
    .click();
  await expect(card.getByText(/OpenCV: 60 × 40/)).toBeVisible();
});

test("offline sign-out and account switching keep pending submissions with their author", async ({
  browser,
}) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  await login(page, "citizen");
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
  await page.reload();
  await page.waitForFunction(() => !!navigator.serviceWorker.controller);
  await context.setOffline(true);
  await page.goto("/reports");
  await page
    .getByLabel("Location", { exact: true })
    .fill("Author scoped offline incident");
  await page.getByLabel("Latitude", { exact: true }).fill("25.297");
  await page.getByLabel("Longitude", { exact: true }).fill("91.582");
  await page
    .getByLabel("Description", { exact: true })
    .fill(
      "This pending report must remain associated with the citizen account.",
    );
  await page.getByLabel("Confirm observations").check();
  await page
    .getByRole("button", { name: "Submit report", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Report saved to this device" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Sign in", exact: true }),
  ).toBeVisible();
  await context.setOffline(false);
  await login(page, "official");
  await page.getByRole("link", { name: "Offline queue", exact: true }).click();
  await expect(
    page.getByText("Ground Crack · Author scoped offline incident", {
      exact: true,
    }),
  ).toHaveCount(0);
  await expect(page.getByText("No records yet", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await login(page, "citizen");
  await page.getByRole("link", { name: "Reports", exact: true }).click();
  await expect(
    page.getByText("Ground Crack · Author scoped offline incident", {
      exact: true,
    }),
  ).toHaveCount(1);
  await context.close();
});
