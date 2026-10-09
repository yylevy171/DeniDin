import { defineConfig, devices } from "@playwright/test";

/**
 * Feature 089 — Agreements acceptance suite (UAT 1.x, 2.x, 3.x, 4.1, 6.1 and the UI halves of
 * 4.2 / 4.3).   npx playwright test -c playwright.agreements.config.ts
 *
 * Real stack, no stand-in server: agreements_serve.sh seeds a throwaway data root and starts
 * denidin-app's real Agreements API (:8310) and the real webapp backend (:8133) wired to it; a
 * Vite dev server (:4175) serves the real frontend. Tests assert on the real ledger files in
 * the throwaway data root. No Morning sandbox is needed (the official client list is injected
 * into the backend by agreements_backend.py).
 */
export const AGREEMENTS_API = "http://127.0.0.1:8133";
export const AGREEMENTS_BASE = "http://localhost:4175";

export default defineConfig({
  testDir: "./tests-agreements",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report-agreements" }]],
  timeout: 60_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: AGREEMENTS_BASE,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    locale: "he-IL",
    timezoneId: "Asia/Jerusalem",
  },
  projects: [{ name: "desktop-chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 900 } } }],
  webServer: [
    {
      command: "bash agreements_serve.sh",
      // 401 (no session) is a "ready" answer for Playwright; /health needs Morning, which this suite does not use.
      url: `${AGREEMENTS_API}/api/clients`,
      reuseExistingServer: false, // always re-seed: tests write the DB and the ledger
      timeout: 90_000,
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      command: `npm --prefix ../frontend run dev -- --port 4175 --strictPort`,
      url: AGREEMENTS_BASE,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
