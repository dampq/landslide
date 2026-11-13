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

test("mobile layout, Hindi and Assamese navigation, model version selection", async ({
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
    page.getByRole("option", { name: "V1 — डिफ़ॉल्ट", exact: true }),
  ).toBeAttached();
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
  await expect(deployment.getByText("Assigned", { exact: true })).toBeVisible();
  await deployment
    .getByRole("button", { name: "En Route", exact: true })
    .click();
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

test("supplied V1 and V2 scores use their own feature forms and preserve imputation", async ({
  page,
}) => {
  await login(page, "official");
  await page
    .getByRole("link", { name: "Model integration", exact: true })
    .click();
  await expect(page.getByLabel("Model version", { exact: true })).toHaveValue(
    "1",
  );
  const location = page.getByLabel("Location", { exact: true });
  await location.selectOption({ index: 1 });
  for (const [name, value] of Object.entries({
    worldcover_class: 10,
    clay_fraction: 0.199,
    sand_fraction: 0.367,
    soil_ph: 5.5,
    soc_stock_t_ha: 170,
  })) {
    await page.locator(`input[name="${name}"]`).fill(String(value));
  }
  await page
    .getByLabel("Feature collection time", { exact: true })
    .fill("2026-11-01T12:00");
  await page
    .getByLabel("Source", { exact: true })
    .fill("Handoff test example; not a field observation");
  await page
    .getByRole("button", { name: "Submit prediction", exact: true })
    .click();
  await expect(page.getByText(/Relative score 0.7506/)).toBeVisible();
  await page.getByLabel("Model version", { exact: true }).selectOption("2");
  await expect(page.locator('input[name="aspect_cos"]')).toBeVisible();
  await page.locator('input[name="worldcover_class"]').fill("10");
  await page
    .getByLabel("Feature collection time", { exact: true })
    .fill("2026-11-01T12:00");
  await page
    .getByLabel("Source", { exact: true })
    .fill("Handoff null-imputation test");
  await page
    .getByRole("button", { name: "Submit prediction", exact: true })
    .click();
  await expect(page.getByText(/Imputed fields: clay_fraction/)).toBeVisible();
  await expect(page.getByText(/Relative score/).first()).toBeVisible();
});

test("supplied examples reproduce V1 reference without a monitoring location", async ({
  page,
}) => {
  await login(page, "official");
  await page
    .getByRole("link", { name: "Model integration", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Load supplied example", exact: true })
    .click();
  await expect(
    page.getByText("Expected reference score: 0.7506392613449581", {
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Run supplied example", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Relative score 0.75063926" }),
  ).toBeVisible();
  await expect(
    page.getByRole("columnheader", { name: "Recall", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Model version", { exact: true }).selectOption("2");
  await expect(
    page.getByRole("button", { name: "Run supplied example", exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Load supplied example", exact: true })
    .click();
  await expect(
    page.getByText("Expected reference score: Not provided", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Run supplied example", exact: true })
    .click();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Supplied demonstration example" }),
  ).toBeVisible();
});

test("report-first verification and assignment needs no monitoring location", async ({
  page,
}) => {
  await login(page, "official");
  const teamSetup = await page.request.post("/api/records/teams", {
    data: {
      name: "Dispatch browser team",
      source: "Synthetic browser test",
      simulated: true,
    },
  });
  const newTeam = await teamSetup.json();
  const created = await page.request.post("/api/reports", {
    data: {
      clientId: "response-workflow-browser",
      incident: "Road Blockage",
      location: "Pilot incident location",
      lat: 25.297,
      lng: 91.582,
      gpsAccuracyM: 25,
      severity: "High",
      description: "Safe labelled browser response demonstration incident.",
    },
  });
  const r = await created.json();
  // Dispatch must use incident coordinates and must not request a Location control.
  await page.getByRole("link", { name: "Reports", exact: true }).click();
  const card = page
    .locator(".rounded-2xl")
    .filter({
      has: page.getByText("Road Blockage · Pilot incident location", {
        exact: true,
      }),
    })
    .last();
  await card.getByRole("link", { name: "Plan response", exact: true }).click();
  await expect(
    page.getByText(`Report ID: ${r.id}`, { exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Location", { exact: true })).toHaveCount(0);
  await page
    .getByLabel("Review note", { exact: true })
    .fill("Reviewed for the safe presentation response");
  await page.getByLabel("Team", { exact: true }).selectOption(newTeam.id);
  await expect(
    page.getByRole("button", { name: "Verify and assign", exact: true }),
  ).toBeDisabled();
  await page.getByLabel("I confirm this destination", { exact: true }).check();
  await page.getByLabel("I confirm this team", { exact: true }).check();
  await page
    .getByRole("button", { name: "Verify and assign", exact: true })
    .click();
  const deployment = page
    .locator(".rounded-2xl")
    .filter({
      has: page.getByText(/Dispatch browser team · /),
    })
    .last();
  await expect(deployment.getByText(/ · Assigned$/).first()).toBeVisible();
  await deployment
    .getByRole("button", { name: "En Route", exact: true })
    .click();
  await deployment
    .getByRole("button", { name: "On Site", exact: true })
    .click();
  await deployment
    .getByRole("button", { name: "Completed", exact: true })
    .click();
  await expect(deployment.getByText(/ · Completed$/).first()).toBeVisible();
});

test("urgent unverified dispatch records a reason and destination correction", async ({
  page,
}) => {
  await login(page, "official");
  const teamSetup = await page.request.post("/api/records/teams", {
    data: {
      name: "Urgent investigation team",
      source: "Synthetic browser test",
      simulated: true,
    },
  });
  const newTeam = await teamSetup.json();
  const created = await page.request.post("/api/reports", {
    data: {
      clientId: "urgent-browser-incident",
      incident: "Other",
      location: "Investigation location",
      lat: 25.3,
      lng: 91.6,
      severity: "High",
      description: "An unconfirmed incident needing investigation.",
    },
  });
  const r = await created.json();
  await page.goto(`/response?reportId=${r.id}`);
  await page
    .getByLabel("Review note", { exact: true })
    .fill("Investigation required before confirmation");
  await page.getByLabel("Destination latitude", { exact: true }).fill("25.31");
  await page
    .getByLabel("Destination correction reason", { exact: true })
    .fill("Confirmed access point with the reporter");
  await page.getByLabel("Team", { exact: true }).selectOption(newTeam.id);
  await page
    .getByLabel("Dispatch decision", { exact: true })
    .selectOption("urgent-unverified");
  await page
    .getByLabel("Urgent dispatch reason", { exact: true })
    .fill("Potential immediate danger warrants investigation");
  await page.getByLabel("I confirm this destination", { exact: true }).check();
  await page.getByLabel("I confirm this team", { exact: true }).check();
  await page
    .getByRole("button", { name: "Assign urgent investigation", exact: true })
    .click();
  await expect(
    page.getByText("Awaiting Verification · Investigation location", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByText(
      "Urgent unverified dispatch: Potential immediate danger warrants investigation",
      { exact: true },
    ),
  ).toBeVisible();
});

test("no configured teams, busy teams and coverage exclusions still permit verification", async ({
  page,
}) => {
  await login(page, "official");
  const response = await page.request.post("/api/reports", {
    data: {
      clientId: "no-teams-browser-case",
      incident: "Other",
      location: "Unassigned incident",
      lat: 25.3,
      lng: 91.6,
      severity: "Low",
      description: "An incident can be reviewed without a configured team.",
    },
  });
  const item = await response.json();
  const path = "**/api/records/teams?limit=500";
  await page.route(path, (route) =>
    route.fulfill({ json: { items: [], total: 0 } }),
  );
  await page.goto(`/response?reportId=${item.id}`);
  await expect(
    page.getByText(
      "No teams configured. You can verify without dispatch; use team setup to register a team.",
      { exact: true },
    ),
  ).toBeVisible();
  await page
    .getByLabel("Review note", { exact: true })
    .fill("Reviewed and pending availability of a team");
  await page.getByRole("button", { name: "Verify only", exact: true }).click();
  await expect(
    page.getByText("Verified · Unassigned incident", { exact: true }),
  ).toBeVisible();
  await page.unroute(path);
  await page.route(path, (route) =>
    route.fulfill({
      json: {
        items: [{ id: "busy-team", name: "Busy team", status: "Assigned" }],
        total: 1,
      },
    }),
  );
  await page.reload();
  await expect(
    page.getByText(
      "All teams are busy. Verification can proceed without dispatch.",
      { exact: true },
    ),
  ).toBeVisible();
  await page.unroute(path);
  await page.route(path, (route) =>
    route.fulfill({
      json: {
        items: [
          {
            id: "outside-team",
            name: "Outside team",
            status: "Available",
            coverageWest: 0,
            coverageSouth: 0,
            coverageEast: 1,
            coverageNorth: 1,
          },
        ],
        total: 1,
      },
    }),
  );
  await page.reload();
  await expect(
    page.getByText(
      "No available team covers this destination under its configured bounds.",
      { exact: true },
    ),
  ).toBeVisible();
});

test("inline team setup preserves a corrected destination and review note", async ({
  page,
}) => {
  await login(page, "official");
  const made = await page.request.post("/api/reports", {
    data: {
      clientId: "inline-team-report",
      incident: "Other",
      location: "Inline setup destination",
      lat: 12.983753,
      lng: 77.675811,
      severity: "Low",
      description: "A safe presentation report used for inline team setup.",
    },
  });
  const report = await made.json();
  let saved = false;
  await page.route("**/api/records/teams?limit=500", (route) =>
    saved ? route.continue() : route.fulfill({ json: { items: [], total: 0 } }),
  );
  await page.goto(`/response?reportId=${report.id}`);
  await page
    .getByLabel("Review note", { exact: true })
    .fill("Preserve this review during team setup");
  await page.getByLabel("Destination latitude", { exact: true }).fill("12.984");
  await page
    .getByLabel("Destination correction reason", { exact: true })
    .fill("Reporter confirmed the corrected access point");
  await page
    .getByRole("button", { name: "Register a team here", exact: true })
    .click();
  await page
    .getByLabel("Team name", { exact: true })
    .fill("Presentation practice team");
  await page
    .getByLabel("Team information source", { exact: true })
    .fill("Explicit synthetic browser demonstration");
  await page.getByLabel("This is a practice team", { exact: true }).check();
  const created = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/records/teams") && r.request().method() === "POST",
  );
  saved = true;
  await page.getByRole("button", { name: "Save team", exact: true }).click();
  const team = await (await created).json();
  expect(team.simulated).toBe(true);
  await expect(page.getByLabel("Team", { exact: true })).toHaveValue(team.id);
  await expect(page.getByLabel("Review note", { exact: true })).toHaveValue(
    "Preserve this review during team setup",
  );
  await expect(
    page.getByLabel("Destination latitude", { exact: true }),
  ).toHaveValue("12.984");
  await expect(
    page.getByLabel("I confirm this team", { exact: true }),
  ).not.toBeChecked();
  await expect(
    page.getByRole("button", { name: "Verify and assign", exact: true }),
  ).toBeDisabled();
  await page.getByLabel("I confirm this destination", { exact: true }).check();
  await page.getByLabel("I confirm this team", { exact: true }).check();
  await page
    .getByRole("button", { name: "Verify and assign", exact: true })
    .click();
  await expect(
    page.getByText("Presentation practice team · Assigned", { exact: true }),
  ).toBeVisible();
});

test("map assessment selection inspects data explicitly and reports unavailable rasters", async ({
  page,
}) => {
  await login(page, "official");
  let extractions = 0;
  await page.route("**/api/assessment/features", (route) => {
    extractions++;
    return route.fulfill({
      status: 503,
      json: {
        detail:
          "Raster data are not prepared. Run npm run prepare:rasters on this server.",
      },
    });
  });
  await page
    .getByRole("navigation", { name: "Main navigation" })
    .getByRole("link", { name: "GIS map", exact: true })
    .click();
  await page
    .locator(".leaflet-container")
    .click({ position: { x: 140, y: 120 } });
  const inspect = page.getByRole("link", {
    name: /Inspect environmental inputs here/,
  });
  await expect(inspect).toBeVisible();
  await inspect.click();
  await expect(
    page.getByRole("heading", {
      name: "Location-based assessment",
      exact: true,
    }),
  ).toBeVisible();
  const url = new URL(page.url());
  await expect(
    page.getByLabel("Assessment latitude", { exact: true }),
  ).toHaveValue(url.searchParams.get("lat")!);
  expect(extractions).toBe(0);
  await page
    .getByRole("button", { name: "Extract environmental inputs", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Raster data are not prepared",
  );
  expect(extractions).toBe(1);
  await expect(
    page.getByRole("button", { name: "Run inspected assessment", exact: true }),
  ).toHaveCount(0);
});

test("citizen map picks require confirmation, cancel preserves GPS and submitted coordinates persist", async ({
  browser,
}) => {
  const context = await browser.newContext({
    geolocation: { latitude: 25.297, longitude: 91.582, accuracy: 12 },
    permissions: ["geolocation"],
  });
  const page = await context.newPage();
  await login(page, "citizen");
  await page.getByRole("link", { name: "Reports", exact: true }).click();
  await page.getByRole("button", { name: "Use my GPS", exact: true }).click();
  await expect(page.getByLabel("Latitude", { exact: true })).toHaveValue(
    "25.297000",
  );
  await page
    .getByRole("button", { name: "Select coordinates on map", exact: true })
    .click();
  let picker = page.getByRole("group", {
    name: "Coordinate map picker",
    exact: true,
  });
  await picker
    .locator(".leaflet-container")
    .click({ position: { x: 210, y: 110 } });
  await expect(page.getByLabel("Latitude", { exact: true })).toHaveValue(
    "25.297000",
  );
  await picker
    .getByRole("button", { name: "Cancel map selection", exact: true })
    .click();
  await expect(page.getByLabel("Longitude", { exact: true })).toHaveValue(
    "91.582000",
  );
  await page
    .getByRole("button", { name: "Select coordinates on map", exact: true })
    .click();
  picker = page.getByRole("group", {
    name: "Coordinate map picker",
    exact: true,
  });
  await picker
    .locator(".leaflet-container")
    .click({ position: { x: 230, y: 120 } });
  await picker
    .getByRole("button", { name: "Use selected coordinates", exact: true })
    .click();
  const lat = Number(
    await page.getByLabel("Latitude", { exact: true }).inputValue(),
  );
  const lng = Number(
    await page.getByLabel("Longitude", { exact: true }).inputValue(),
  );
  expect(lat).not.toBe(25.297);
  await page
    .getByLabel("Location", { exact: true })
    .fill("Map chosen incident");
  await page
    .getByLabel("Description", { exact: true })
    .fill("Safe browser demonstration using a confirmed map pin.");
  await page.getByLabel("Confirm observations").check();
  const response = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/reports") &&
      r.request().method() === "POST" &&
      r.request().postDataJSON().location === "Map chosen incident",
  );
  await page
    .getByRole("button", { name: "Submit report", exact: true })
    .click();
  const saved = await (await response).json();
  expect(saved.lat).toBe(lat);
  expect(saved.lng).toBe(lng);
  expect(saved.gpsAccuracyM).toBeNull();
  await context.close();
});

test("coordinate record forms share the picker and preserve edits and other fields", async ({
  page,
}) => {
  await login(page, "official");
  await page.getByRole("link", { name: "Monitoring", exact: true }).click();
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await page
    .getByLabel("Name", { exact: true })
    .fill("Map picker monitoring point");
  await page.getByLabel("District", { exact: true }).fill("Test district");
  await page.getByLabel("State", { exact: true }).fill("Meghalaya");
  await page
    .getByRole("button", { name: "Select coordinates on map", exact: true })
    .click();
  let picker = page.getByRole("group", {
    name: "Coordinate map picker",
    exact: true,
  });
  await picker
    .locator(".leaflet-container")
    .click({ position: { x: 200, y: 120 } });
  await picker
    .getByRole("button", { name: "Use selected coordinates", exact: true })
    .click();
  await expect(page.getByLabel("Name", { exact: true })).toHaveValue(
    "Map picker monitoring point",
  );
  const lat = Number(
    await page.getByLabel("Latitude", { exact: true }).inputValue(),
  );
  const created = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/records/locations") &&
      r.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Save", exact: true }).click();
  const record = await (await created).json();
  expect(record.lat).toBe(lat);
  const card = page
    .locator(".record-grid .rounded-2xl")
    .filter({
      has: page.getByText("Map picker monitoring point", { exact: true }),
    })
    .last();
  await card.getByRole("button", { name: "Review", exact: true }).click();
  await expect(page.getByLabel("Latitude", { exact: true })).toHaveValue(
    String(lat),
  );
  await page
    .getByRole("button", { name: "Select coordinates on map", exact: true })
    .click();
  picker = page.getByRole("group", {
    name: "Coordinate map picker",
    exact: true,
  });
  await picker
    .locator(".leaflet-container")
    .click({ position: { x: 240, y: 110 } });
  await picker
    .getByRole("button", { name: "Cancel map selection", exact: true })
    .click();
  await expect(page.getByLabel("Latitude", { exact: true })).toHaveValue(
    String(lat),
  );
  await page.getByRole("button", { name: "Close", exact: true }).click();
  for (const tab of ["Roads", "Villages & population", "Infrastructure"]) {
    await page.getByRole("button", { name: tab, exact: true }).click();
    await page.getByRole("button", { name: "Create", exact: true }).click();
    await expect(
      page.getByRole("button", {
        name: "Select coordinates on map",
        exact: true,
      }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Close", exact: true }).click();
  }
  await page
    .getByRole("link", { name: "History & imagery", exact: true })
    .click();
  for (const tab of ["History", "Satellite imagery"]) {
    // Default history tab is already active; satellite is selected explicitly below when present.
    if (tab === "Satellite imagery")
      await page
        .getByRole("button", { name: "Satellite imagery", exact: true })
        .click();
    await page.getByRole("button", { name: "Create", exact: true }).click();
    await expect(
      page.getByRole("button", {
        name: "Select coordinates on map",
        exact: true,
      }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Close", exact: true }).click();
  }
});

test("saved-location map selection uses an existing record and never creates a nearest location", async ({
  page,
}) => {
  await login(page, "official");
  const all = (await (await page.request.get("/api/records/locations")).json())
    .items;
  await page.getByRole("link", { name: "Weather", exact: true }).click();
  await page
    .getByRole("button", { name: "Select saved location on map", exact: true })
    .click();
  const picker = page.getByRole("group", {
    name: "Saved location map picker",
    exact: true,
  });
  await picker
    .locator(".leaflet-container")
    .click({ position: { x: 180, y: 120 } });
  await expect(
    picker.getByRole("button", {
      name: "Use selected saved location",
      exact: true,
    }),
  ).toBeDisabled();
  await picker.locator(".leaflet-interactive").first().click();
  await expect(page.getByLabel("Location", { exact: true })).toHaveValue("");
  await picker
    .getByRole("button", { name: "Use selected saved location", exact: true })
    .click();
  await expect(page.getByLabel("Location", { exact: true })).toHaveValue(
    all[0].id,
  );
  expect(
    (await (await page.request.get("/api/records/locations")).json()).total,
  ).toBe(all.length);
});

test("shared picker updates assessment coordinates and records response corrections with confirmation", async ({
  page,
}) => {
  await login(page, "official");
  await page
    .getByRole("link", { name: "Model integration", exact: true })
    .click();
  let extractions = 0;
  await page.route("**/api/assessment/features", (route) => {
    extractions++;
    return route.fulfill({
      status: 503,
      json: { detail: "Explicit test unavailable state" },
    });
  });
  await page
    .getByRole("button", { name: "Select coordinates on map", exact: true })
    .click();
  let picker = page.getByRole("group", {
    name: "Coordinate map picker",
    exact: true,
  });
  await picker
    .locator(".leaflet-container")
    .click({ position: { x: 220, y: 120 } });
  await expect(
    page.getByLabel("Assessment latitude", { exact: true }),
  ).toHaveValue("");
  await picker
    .getByRole("button", { name: "Use selected coordinates", exact: true })
    .click();
  await expect(
    page.getByLabel("Assessment latitude", { exact: true }),
  ).not.toHaveValue("");
  expect(extractions).toBe(0);
  const team = await (
    await page.request.post("/api/records/teams", {
      data: {
        name: "Map correction team",
        source: "Synthetic browser test",
        simulated: true,
      },
    })
  ).json();
  const item = await (
    await page.request.post("/api/reports", {
      data: {
        clientId: "map-dispatch-correction",
        incident: "Other",
        location: "Map correction incident",
        lat: 25.297,
        lng: 91.582,
        severity: "Low",
        description:
          "Presentation incident with a deliberate map-based correction.",
      },
    })
  ).json();
  await page.goto(`/response?reportId=${item.id}`);
  await page
    .getByLabel("Review note", { exact: true })
    .fill("Review note must survive choosing a pin");
  await page.getByLabel("Team", { exact: true }).selectOption(team.id);
  await page.getByLabel("I confirm this destination", { exact: true }).check();
  await page.getByLabel("I confirm this team", { exact: true }).check();
  await page
    .getByRole("button", { name: "Select coordinates on map", exact: true })
    .click();
  picker = page.getByRole("group", {
    name: "Coordinate map picker",
    exact: true,
  });
  await picker
    .locator(".leaflet-container")
    .click({ position: { x: 230, y: 120 } });
  await picker
    .getByRole("button", { name: "Use selected coordinates", exact: true })
    .click();
  await expect(page.getByLabel("Review note", { exact: true })).toHaveValue(
    "Review note must survive choosing a pin",
  );
  await expect(
    page.getByLabel("I confirm this destination", { exact: true }),
  ).not.toBeChecked();
  await expect(
    page.getByLabel("I confirm this team", { exact: true }),
  ).not.toBeChecked();
  await expect(
    page.getByRole("button", { name: "Verify and assign", exact: true }),
  ).toBeDisabled();
  await page
    .getByLabel("Destination correction reason", { exact: true })
    .fill("Reporter confirmed the selected access point");
  await page.getByLabel("I confirm this destination", { exact: true }).check();
  await page.getByLabel("I confirm this team", { exact: true }).check();
  const assigned = page.waitForResponse(
    (r) =>
      r.url().endsWith(`/api/reports/${item.id}/dispatch`) &&
      r.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Verify and assign", exact: true })
    .click();
  const d = await (await assigned).json();
  expect(d.reportCoordinates.lat).toBe(item.lat);
  expect(d.lat).not.toBe(item.lat);
  expect(d.correctionReason).toBe(
    "Reporter confirmed the selected access point",
  );
});

test("location details suggestions preserve manual entries and clear derived fields after coordinate changes", async ({
  page,
}) => {
  await login(page, "admin");
  await page.goto("/monitoring");
  await page.getByRole("button", { name: "Create", exact: true }).click();
  const form = page
    .locator("form")
    .filter({ has: page.getByLabel("District", { exact: true }) });
  await form.getByLabel("Name", { exact: true }).fill("Official chosen name");
  await form.getByLabel("Latitude", { exact: true }).fill("26.19");
  await form.getByLabel("Longitude", { exact: true }).fill("91.71");
  let calls = 0;
  await page.route("**/api/location/details", async (route) => {
    calls++;
    expect(route.request().postDataJSON()).toEqual({ lat: 26.19, lng: 91.71 });
    await route.fulfill({
      json: {
        lat: 26.19,
        lng: 91.71,
        fields: {
          name: "Mapped village",
          district: "Mapped district",
          state: "Assam",
          slope: 12.5,
        },
        provenance: {
          name: { source: "Mock provider" },
          district: { source: "Mock provider" },
          state: { source: "Test boundary" },
          slope: { source: "Test terrain", unit: "degrees" },
        },
        unavailable: {},
      },
    });
  });
  await form
    .getByRole("button", { name: "Look up location details", exact: true })
    .click();
  await expect(form.getByText("Mapped village", { exact: true })).toBeVisible();
  await expect(form.getByLabel("District", { exact: true })).toHaveValue("");
  await form
    .getByRole("button", { name: "Apply location suggestions", exact: true })
    .click();
  await expect(form.getByLabel("Name", { exact: true })).toHaveValue(
    "Official chosen name",
  );
  await expect(form.getByLabel("District", { exact: true })).toHaveValue(
    "Mapped district",
  );
  await expect(form.getByLabel("Slope (degrees)", { exact: true })).toHaveValue(
    "12.5",
  );
  await expect(form.getByLabel("Severity", { exact: true })).toHaveValue("Low");
  await form
    .getByLabel("Replace existing values with available suggestions")
    .check();
  await form
    .getByRole("button", { name: "Apply location suggestions", exact: true })
    .click();
  await expect(form.getByLabel("Name", { exact: true })).toHaveValue(
    "Mapped village",
  );
  await form
    .getByLabel("District", { exact: true })
    .fill("Official corrected district");
  await form.getByLabel("Longitude", { exact: true }).fill("92");
  await expect(form.getByLabel("Name", { exact: true })).toHaveValue("");
  await expect(form.getByLabel("State", { exact: true })).toHaveValue("");
  await expect(form.getByLabel("Slope (degrees)", { exact: true })).toHaveValue(
    "",
  );
  await expect(form.getByLabel("District", { exact: true })).toHaveValue(
    "Official corrected district",
  );
  expect(calls).toBe(1);
  await form.getByLabel("Longitude", { exact: true }).fill("91.71");
  await form
    .getByRole("button", { name: "Look up location details", exact: true })
    .click();
  await form
    .getByRole("button", { name: "Apply location suggestions", exact: true })
    .click();
  await form
    .getByLabel("Name", { exact: true })
    .fill("Location lookup browser test");
  const saved = page.waitForResponse(
    (response) =>
      response.url().includes("/api/records/locations") &&
      response.request().method() === "POST",
  );
  await form.getByRole("button", { name: "Save", exact: true }).click();
  const record = await (await saved).json();
  expect(record.locationDetailsProvenance.slope.value).toBe(12.5);
  expect(record.locationDetailsProvenance.name).toBeUndefined();
  expect(record.district).toBe("Official corrected district");
  const card = page
    .locator(".rounded-2xl")
    .filter({
      has: page.getByText("Location lookup browser test", { exact: true }),
    })
    .last();
  await card.getByText("Source details", { exact: true }).click();
  await expect(
    card.getByText("Slope (degrees): Test terrain", { exact: true }),
  ).toBeVisible();
});
