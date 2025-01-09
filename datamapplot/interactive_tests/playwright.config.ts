import { defineConfig } from '@playwright/test';

export default defineConfig({
  use: {
    viewport: { width: 1280, height: 720 },
    screenshot: 'on',
  },
  expect: {
    toHaveScreenshot: {
      maxDiffPixels: 100,
      threshold: 0.2,
      animations: 'disabled',
    }
  },
  webServer: {
    command: 'python -m http.server 8000',
    url: 'http://localhost:8000',
    reuseExistingServer: true,
  },
});