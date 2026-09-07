import { defineConfig, devices } from "@playwright/test";

/**
 * Feature 068 — Ledger Web UI acceptance suite.
 * Full test plan: ../../../specs/in-progress/068-ledger-ui-and-reports/PLAYWRIGHT-TEST-PLAN.md
 *
 * Real stack, no mocking:
 *   - `serve.sh` seeds a deterministic fixture data root and starts two real webapp-backend
 *     instances — :8130 (the "full" fixture) and :8131 (an "empty window" fixture).
 *   - one Vite dev server (:4173) serves the real frontend build; `?api=<origin>` (localhost
 *     only) points it at whichever backend a given test needs.
 */
const FRONTEND_PORT = 4173;
export const FULL_API = "http://127.0.0.1:8130";
export const EMPTY_API = "http://127.0.0.1:8131";
export const BASE = `http://localhost:${FRONTEND_PORT}`;

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  timeout: 30_000,
  expect: { timeout: 7_000, toHaveScreenshot: { maxDiffPixelRatio: 0.02 } },
  use: {
    baseURL: BASE,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    locale: "he-IL",
    timezoneId: "Asia/Jerusalem",
  },
  projects: [
    {
      name: "desktop-chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 900 } },
      testIgnore: /06-mobile\.spec\.ts/, // Component 6 is mobile-only — runs under mobile-chromium
    },
    { name: "mobile-chromium", use: { ...devices["Pixel 7"] }, testMatch: /06-mobile\.spec\.ts/ },
  ],
  webServer: [
    {
      command: "bash serve.sh",
      url: `${FULL_API}/health`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      command: `npm --prefix ../frontend run dev -- --port ${FRONTEND_PORT} --strictPort`,
      url: BASE,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
