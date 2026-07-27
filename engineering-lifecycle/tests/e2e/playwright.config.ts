import { defineConfig, devices } from '@playwright/test';

// The dashboard is a single self-contained HTML file with inline CSS and JS, so
// there is no server to start: specs open it over file://. That also means the
// fixture must be generated before the run (npm run fixture).
export default defineConfig({
  testDir: '.',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['html', { open: 'never' }], ['list']] : 'list',
  use: {
    // Recording always is slow and produces artifacts nobody reads.
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
