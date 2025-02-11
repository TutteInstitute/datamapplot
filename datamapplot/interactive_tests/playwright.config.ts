import { defineConfig } from '@playwright/test';
import path from 'path';

const htmlDir = path.resolve(__dirname, '../tests/html');
const projDir = path.resolve(__dirname, '../..');

console.log(`Resolved htmlDir: ${htmlDir}`);
console.log(`Resolved htmlDir: ${projDir}`);

export default defineConfig({
  use: {
    viewport: { width: 1280, height: 720 },
    screenshot: 'on',
    headless: true,
  },
  expect: {
    timeout: 180_000,
    toHaveScreenshot: {
      maxDiffPixels: 30_000, // This is the total pixel difference threshold
      threshold: 0.2, // This is the per pixel color difference threshold
      animations: 'disabled',
    }
  },
  webServer: {
    command: `python -m http.server 8000 -d ${htmlDir}`,
    url: 'http://localhost:8000',
    reuseExistingServer: true,
    timeout: 120000
  },
  workers: process.env.CI ? 1 : undefined, // Run tests sequentially in CI
  reporter: [['junit', { outputFile: `${projDir}/test-results/e2e-junit-results.xml` }], ['html', { open: 'never' }]],
});