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
  await page.getByRole("button", { name: "मेनू", exact: true }).click();
  await page.getByRole("link", { name: "मॉडल एकीकरण", exact: true }).click();
  await expect(
    page.getByText("मॉडल उपलब्ध नहीं है", { exact: true }),
  ).toBeVisible();
  await page.getByLabel("भाषा", { exact: true }).selectOption("as");
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

test("blocked basemap displays a clear notice instead of 403 images while retaining GIS records", async ({
  page,
}) => {
  await page.route("https://tile.openstreetmap.org/**", (route) =>
    route.fulfill({
      status: 403,
      contentType: "text/plain",
      headers: { "access-control-allow-origin": "*" },
      body: "Access blocked",
    }),
  );
  await login(page, "official");
  await page
    .getByRole("navigation", { name: "Main navigation" })
    .getByRole("link", { name: "GIS map", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({
      hasText: "OpenStreetMap refused the background map request (HTTP 403)",
    }),
  ).toBeVisible();
  await expect(page.locator(".leaflet-interactive")).not.toHaveCount(0);
  await expect(page.locator("img.leaflet-tile")).toHaveCount(0);
  await expect(page.locator("path.reference-state")).toHaveCount(8);
  await page.screenshot({
    path: "test-results/reference-map-desktop.png",
    fullPage: true,
  });
});

test("a real regional reference map is available offline, independently of third-party tiles", async ({
  browser,
}) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  await login(page, "official");
  await page
    .getByRole("navigation", { name: "Main navigation" })
    .getByRole("link", { name: "GIS map", exact: true })
    .click();
  await page
    .getByLabel("Background map", { exact: true })
    .selectOption("reference");
  await expect(page.locator("path.reference-state")).toHaveCount(8);
  await expect(page.getByText("Assam", { exact: true })).toBeVisible();
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
  await page.reload();
  await page.waitForFunction(() => !!navigator.serviceWorker.controller);
  await context.setOffline(true);
  await page.reload();
  await expect(page.locator("path.reference-state")).toHaveCount(8);
  await expect(page.getByText("Meghalaya", { exact: true })).toBeVisible();
  await expect(page.locator(".leaflet-control-attribution")).toContainText(
    "Natural Earth",
  );
  await page.screenshot({
    path: "test-results/offline-reference-map.png",
    fullPage: true,
  });
  await context.close();
});

test("weather failures keep labelled samples, and officials can explicitly refresh the demonstration", async ({
  page,
}) => {
  await login(page, "official");
  await page.getByRole("link", { name: "Weather", exact: true }).click();
  await page
    .getByLabel("Location", { exact: true })
    .selectOption("demo-location-0");
  await expect(
    page.getByText("Sample weather — simulated", { exact: true }),
  ).toBeVisible();
  await page.route("**/api/weather/*/refresh", (route) =>
    route.fulfill({
      status: 502,
      contentType: "application/json",
      body: JSON.stringify({
        detail:
          "Weather provider unavailable; cached values, if any, are retained. Check network access to api.open-meteo.com.",
      }),
    }),
  );
  await page
    .getByRole("button", { name: "Refresh forecast", exact: true })
    .click();
  await expect(
    page.getByRole("alert").filter({ hasText: "Weather provider unavailable" }),
  ).toBeVisible();
  await expect(
    page.getByText("Sample weather — simulated", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Load sample weather", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Saved" }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "These invented values demonstrate the website. They are not current conditions and must not be used for warnings.",
      { exact: true },
    ),
  ).toBeVisible();
});

test("officials assign and complete a response deployment through the portal", async ({
  page,
}) => {
  await login(page, "official");
  await page.getByRole("link", { name: "Response", exact: true }).click();
  await page
    .getByLabel("Location", { exact: true })
    .selectOption("demo-location-0");
  await page.getByLabel("Team", { exact: true }).selectOption("demo-team-0");
  await page.getByRole("button", { name: "Deploy", exact: true }).click();
  const deployment = page
    .locator(".rounded-2xl")
    .filter({
      has: page.getByText("Mawsynram demonstration response team → Mawsynram", {
        exact: true,
      }),
    })
    .last();
  await expect(deployment.getByText("En Route", { exact: true })).toBeVisible();
  await deployment
    .getByRole("button", { name: "On Site", exact: true })
    .click();
  await expect(deployment.getByText("On Site", { exact: true })).toBeVisible();
  await deployment
    .getByRole("button", { name: "Completed", exact: true })
    .click();
  await expect(
    deployment.getByText("Completed", { exact: true }),
  ).toBeVisible();
  await expect(
    page
      .getByLabel("Team", { exact: true })
      .locator('option[value="demo-team-0"]'),
  ).toHaveCount(1);
});

test("administrator imports attributed records, downloads CSV, and assigns a portal role", async ({
  browser,
}) => {
  const context = await browser.newContext();
  const page = await context.newPage();
  await login(page, "admin");
  const email = "browser-role-check@e2e.test";
  expect(
    (
      await page.request.post("/api/auth/register", {
        data: {
          email,
          name: "Browser role check",
          password: "e2e-test-password-only",
        },
      })
    ).status(),
  ).toBe(201);
  await page.getByRole("link", { name: "Administration", exact: true }).click();
  await page
    .getByLabel("Role for " + email, { exact: true })
    .selectOption("official");
  await expect(
    page.getByRole("status").filter({ hasText: "Saved" }),
  ).toBeVisible();
  await page
    .getByLabel("Import collection", { exact: true })
    .selectOption("history");
  await page.getByLabel("JSON / GeoJSON", { exact: true }).fill(
    JSON.stringify({
      items: [
        {
          name: "Browser imported demonstration event",
          lat: 25.297,
          lng: 91.582,
          observedAt: 1750000000,
          source: "Browser test synthetic dataset",
          simulated: true,
        },
      ],
    }),
  );
  await page.getByRole("button", { name: "Import data", exact: true }).click();
  await expect(
    page.getByText("1 imported; 0 unchanged", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("link", { name: "History & imagery", exact: true })
    .click();
  await expect(
    page.getByText("Browser imported demonstration event", { exact: true }),
  ).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("link", { name: "Download CSV", exact: true }).click();
  const download = await downloadPromise;
  const fs = await import("node:fs/promises");
  const csv = await fs.readFile((await download.path())!, "utf8");
  expect(csv).toContain("Browser imported demonstration event");
  expect(csv).toContain("simulated");
  expect(csv).toContain("Browser test synthetic dataset");
  const official = await browser.newContext();
  const newPage = await official.newPage();
  await newPage.goto("/login");
  await newPage.getByLabel("Email", { exact: true }).fill(email);
  await newPage
    .getByLabel("Password", { exact: true })
    .fill("e2e-test-password-only");
  await newPage.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    newPage.getByRole("link", { name: "Response", exact: true }),
  ).toBeVisible();
  await expect(
    newPage.getByRole("link", { name: "Administration", exact: true }),
  ).toHaveCount(0);
  await official.close();
  await context.close();
});

test("Hindi and Assamese cover all portal pages and keep report field values independent of translations", async ({
  page,
}) => {
  await login(page, "admin");
  const headings: Record<string, string[]> = {
    hi: [
      "डैशबोर्ड",
      "जीआईएस मानचित्र",
      "घटना रिपोर्ट",
      "पर्यावरण निगरानी",
      "मौसम",
      "मॉडल एकीकरण",
      "चेतावनियाँ",
      "आपात प्रतिक्रिया",
      "इतिहास और उपग्रह चित्र",
      "विश्लेषण",
      "ऑफ़लाइन कतार",
      "प्रशासन",
      "सेटिंग्स",
    ],
    as: [
      "ডেশ্বব’ৰ্ড",
      "জিআইএছ মানচিত্ৰ",
      "ঘটনাৰ প্ৰতিবেদন",
      "পৰিৱেশ নিৰীক্ষণ",
      "বতৰ",
      "মডেল সংযোগ",
      "সতৰ্কবাণী",
      "জৰুৰী সঁহাৰি",
      "ইতিহাস আৰু উপগ্ৰহ চিত্ৰ",
      "বিশ্লেষণ",
      "অফলাইন শাৰী",
      "প্ৰশাসন",
      "ছেটিংছ",
    ],
  };
  for (const lang of ["hi", "as"]) {
    await page.locator("header select").selectOption(lang);
    for (const title of headings[lang]) {
      await page
        .locator("aside nav")
        .getByRole("link", { name: title, exact: true })
        .click();
      await expect(
        page.getByRole("heading", { level: 1, name: title, exact: true }),
      ).toBeVisible();
    }
  }
  await page.locator("header select").selectOption("hi");
  await page
    .locator("aside nav")
    .getByRole("link", { name: "घटना रिपोर्ट", exact: true })
    .click();
  await page
    .getByLabel("घटना का प्रकार", { exact: true })
    .selectOption("Road Blockage");
  await expect(page.getByLabel("घटना का प्रकार", { exact: true })).toHaveValue(
    "Road Blockage",
  );
  await expect(
    page
      .getByLabel("घटना का प्रकार", { exact: true })
      .locator("option:checked"),
  ).toHaveText("सड़क अवरोध");
  await page.screenshot({
    path: "test-results/hindi-report.png",
    fullPage: true,
  });
});

test("permitted online tiles render with attribution and can switch back to the bundled reference", async ({
  page,
}) => {
  await page.route("https://tile.openstreetmap.org/**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "image/png",
      headers: { "access-control-allow-origin": "*" },
      path: "tests/fixtures/field-sample.png",
    }),
  );
  await login(page, "official");
  await page
    .getByRole("navigation", { name: "Main navigation" })
    .getByRole("link", { name: "GIS map", exact: true })
    .click();
  await expect(page.locator("img.leaflet-tile-loaded")).not.toHaveCount(0);
  await expect(page.locator(".leaflet-control-attribution")).toContainText(
    "OpenStreetMap",
  );
  await expect(page.locator("path.reference-state")).toHaveCount(0);
  await page
    .getByLabel("Background map", { exact: true })
    .selectOption("reference");
  await expect(page.locator("path.reference-state")).toHaveCount(8);
  await expect(page.getByText("Assam", { exact: true })).toBeVisible();
  await expect(page.locator(".leaflet-control-attribution")).toContainText(
    "Natural Earth",
  );
});

test("cancelling sample replacement preserves the live view and never reports a save", async ({
  page,
}) => {
  await login(page, "official");
  const cache = await (
    await page.request.get("/api/weather/demo-location-0")
  ).json();
  await page.route("**/api/weather/demo-location-0", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        ...cache,
        simulated: false,
        source: "Test live-provider fixture",
      }),
    }),
  );
  let sampleRequests = 0;
  page.on("request", (request) => {
    if (request.url().endsWith("/sample") && request.method() === "POST")
      sampleRequests++;
  });
  await page.getByRole("link", { name: "Weather", exact: true }).click();
  await page
    .getByLabel("Location", { exact: true })
    .selectOption("demo-location-0");
  await expect(
    page.getByText("Open-Meteo weather — modelled", { exact: true }),
  ).toBeVisible();
  page.once("dialog", (dialog) => dialog.dismiss());
  await page
    .getByRole("button", { name: "Load sample weather", exact: true })
    .click();
  await expect(
    page.getByText("Open-Meteo weather — modelled", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("status").filter({ hasText: "Saved" }),
  ).toHaveCount(0);
  expect(sampleRequests).toBe(0);
});

test("sign-in and registration always show in-page validation instead of silently blocking submission", async ({
  page,
}) => {
  await page.goto("/login");
  let registrationRequests = 0;
  page.on("request", (r) => {
    if (r.url().endsWith("/api/auth/register") && r.method() === "POST")
      registrationRequests++;
  });
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Enter a valid email address.",
  );
  await page.getByLabel("Email", { exact: true }).fill("not-an-email");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Enter a valid email address.",
  );
  await page.getByLabel("Email", { exact: true }).fill("citizen@e2e.test");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Enter your password.");
  await page.getByLabel("Password", { exact: true }).fill("short");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Invalid email or password",
  );
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await page.getByRole("button", { name: "Register", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText("Enter your name.");
  await page.getByLabel("Name", { exact: true }).fill("Browser validation");
  await page.getByRole("button", { name: "Register", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Use at least 12 characters",
  );
  expect(registrationRequests).toBe(0);
  await page.locator("header select").selectOption("hi");
  await expect(page.getByRole("alert")).toContainText("नए खाते के पासवर्ड");
});

test("a new citizen registers through the real form, retains the session across reload, and signs in again", async ({
  page,
  context,
}) => {
  const email = "ui-registration-check@e2e.test";
  await page.goto("/login");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await page
    .getByLabel("Name", { exact: true })
    .fill("UI registration citizen");
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page
    .getByLabel("Password", { exact: true })
    .fill("browser-registration-password");
  await page.getByRole("button", { name: "Register", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Dashboard", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("UI registration citizen", { exact: true }),
  ).toBeVisible();
  const cookie = (await context.cookies()).find(
    (c) => c.name === "ashtaraksha_session",
  );
  expect(cookie?.httpOnly).toBe(true);
  expect(cookie?.sameSite).toBe("Strict");
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Dashboard", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Sign in", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Email", { exact: true }).fill(email);
  await page
    .getByLabel("Password", { exact: true })
    .fill("browser-registration-password");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Dashboard", exact: true }),
  ).toBeVisible();
});

test("blocked session cookies produce a clear error rather than a dashboard/sign-in loop", async ({
  page,
}) => {
  await page.route("**/api/auth/login", async (route) => {
    const response = await route.fetch();
    const headers = { ...response.headers() };
    delete headers["set-cookie"];
    // route.fetch uses Playwright's shared cookie jar; remove that side effect
    // as well as the browser response header to simulate an actual cookie block.
    await page.context().clearCookies({ name: "ashtaraksha_session" });
    await route.fulfill({ response, headers });
  });
  await page.goto("/login");
  await page.getByLabel("Email", { exact: true }).fill("citizen@e2e.test");
  await page
    .getByLabel("Password", { exact: true })
    .fill("e2e-test-password-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Your browser did not retain the sign-in session",
  );
  await expect(
    page.getByRole("heading", { name: "Sign in", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeEnabled();
});

test("a sign-in service failure is actionable and the form can be retried", async ({
  page,
}) => {
  await page.route("**/api/auth/login", (route) =>
    route.fulfill({
      status: 503,
      contentType: "text/plain",
      body: "Temporarily unavailable",
    }),
  );
  await page.goto("/login");
  await page.getByLabel("Email", { exact: true }).fill("citizen@e2e.test");
  await page
    .getByLabel("Password", { exact: true })
    .fill("e2e-test-password-only");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Sign-in is temporarily unavailable.",
  );
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeEnabled();
  await page.unroute("**/api/auth/login");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Dashboard", exact: true }),
  ).toBeVisible();
});

test("a stalled sign-in request times out with a visible message and restores the submit button", async ({
  page,
}) => {
  await page.goto("/login");
  await page.clock.install();
  await page.route("**/api/auth/login", () => {});
  await page.getByLabel("Email", { exact: true }).fill("citizen@e2e.test");
  await page
    .getByLabel("Password", { exact: true })
    .fill("e2e-test-password-only");
  const request = page.waitForRequest(
    (r) => r.url().endsWith("/api/auth/login") && r.method() === "POST",
  );
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await request;
  await page.clock.fastForward(15001);
  await expect(page.getByRole("alert")).toContainText(
    "The sign-in service is taking too long.",
  );
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeEnabled();
});

test("successful registration remains clearly confirmed when automatic sign-in fails, and retry uses the created account", async ({
  page,
}) => {
  await page.route("**/api/auth/login", (route) =>
    route.fulfill({
      status: 503,
      contentType: "text/plain",
      body: "Temporarily unavailable",
    }),
  );
  await page.goto("/login");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await page
    .getByLabel("Name", { exact: true })
    .fill("Registration retry citizen");
  await page
    .getByLabel("Email", { exact: true })
    .fill("registration-retry@e2e.test");
  await page
    .getByLabel("Password", { exact: true })
    .fill("browser-registration-password");
  await page.getByRole("button", { name: "Register", exact: true }).click();
  await expect(page.getByRole("status")).toContainText(
    "Your account was created.",
  );
  await expect(page.getByRole("alert")).toContainText(
    "Sign-in is temporarily unavailable.",
  );
  await page.unroute("**/api/auth/login");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Dashboard", exact: true }),
  ).toBeVisible();
});
