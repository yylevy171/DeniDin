import { defineConfig, devices } from "@playwright/test";

/**
 * Feature 087 — Clients tab acceptance suite (UAT-1/2/3 + the in-memory-caching behavior).
 * Separate from playwright.config.ts (the Feature 068 suite, untouched):
 *   npx playwright test -c playwright.clients.config.ts
 *
 * Real stack, no mocking: clients_serve.sh seeds .fixture/clients and starts a real
 * webapp-backend on :8132 wired to the Morning SANDBOX; a Vite dev server on :4174 serves the
 * real frontend (`?api=<origin>` points it at that backend).
 */
export const CLIENTS_API = "http://127.0.0.1:8132";
export const CLIENTS_BASE = "http://localhost:4174";

export default defineConfig({
  testDir: "./tests-clients",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report-clients" }]],
  timeout: 60_000,
  expect: { timeout: 15_000 }, // the first clients load makes real Morning sandbox calls
  use: {
    baseURL: CLIENTS_BASE,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    locale: "he-IL",
    timezoneId: "Asia/Jerusalem",
  },
  projects: [{ name: "desktop-chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 900 } } }],
  webServer: [
    {
      command: "bash clients_serve.sh",
      url: `${CLIENTS_API}/health`,
      reuseExistingServer: false, // always re-seed: tests write comments/mappings
      timeout: 90_000,
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      command: `npm --prefix ../frontend run dev -- --port 4174 --strictPort`,
      url: CLIENTS_BASE,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
