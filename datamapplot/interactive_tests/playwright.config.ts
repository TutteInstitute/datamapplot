import { defineConfig, devices } from '@playwright/test';
import path from 'path';

const htmlDir = path.resolve(__dirname, '../tests/html');
const projDir = path.resolve(__dirname, '../..');

console.log(`Resolved htmlDir: ${htmlDir}`);
console.log(`Resolved htmlDir: ${projDir}`);

export default defineConfig({
  use: {
    screenshot: 'on',
    headless: true,
  },
  expect: {
    timeout: 180_000,
    toHaveScreenshot: {
      threshold: 0.2, // This is the per pixel color difference threshold
      animations: 'disabled',
    }
  },
  projects: [
    /* Test against desktop browsers */
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1280, height: 720 },
      },
      expect:{
        toHaveScreenshot: {
          maxDiffPixels: 20_000, // This is the total pixel difference threshold
        },
      },
    },
    {
      name: 'firefox',
      use: {
        ...devices['Desktop Firefox'],
        viewport: { width: 1280, height: 720 },
      },
      expect:{
        toHaveScreenshot: {
          maxDiffPixels: 20_000, // This is the total pixel difference threshold
        },
      },
    },
    {
      name: 'webkit',
      use: {
        ...devices['Desktop Safari'],
        viewport: { width: 1280, height: 720 },
      },
      expect:{
        toHaveScreenshot: {
          maxDiffPixels: 20_000, // This is the total pixel difference threshold
        },
      },
    },
    /* Test against mobile viewports. */
    {
      name: 'Mobile Chrome',
      use: {
        ...devices['Pixel 5'],
        viewport: { width: 412, height: 732 },
      },
      expect:{
        toHaveScreenshot: {
          maxDiffPixels: 6_000, // This is the total pixel difference threshold
        },
      },
    },
    {
      name: 'Mobile Safari',
      use: {
        ...devices['iPhone 12'],
        viewport: { width: 390, height: 844 },
      },
      expect:{
        toHaveScreenshot: {
          maxDiffPixels: 6_000, // This is the total pixel difference threshold
        },
      },
    },
  ],
  webServer: {
    command: `python -m http.server 8000 -d ${htmlDir}`,
    url: 'http://localhost:8000',
    reuseExistingServer: true,
    timeout: 120000
  },
  workers: process.env.CI ? 1 : undefined, // Run tests sequentially in CI
  reporter: [['junit', { outputFile: `${projDir}/test-results/e2e-junit-results.xml` }], ['html', { open: 'never' }]],
});