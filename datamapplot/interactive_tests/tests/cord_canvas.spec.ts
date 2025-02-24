import { test, expect } from '@playwright/test';

test.describe('Cord19 Canvas Tests', () => {
  test.beforeEach(async ({ page }, testInfo) => {
    // Extend timeout for all tests running this hook by 5 minutes.
    testInfo.setTimeout(testInfo.timeout + 300_000);
    // Set consistent viewport size
    await page.setViewportSize({ width: 1280, height: 720 });

    // Load the page
    const response = await page.goto('http://localhost:8000/cord19.html', { timeout: 60_000 });
    expect(response.status()).toBe(200);

    // Wait for loading
    console.log('Waiting for #loading and #progress-container to be hidden...');
    await Promise.all([
      page.waitForSelector('#loading', { state: 'hidden', timeout: 120_000 }),
      page.waitForSelector('#progress-container', { state: 'hidden', timeout: 120_000 })
    ]);
  });

  const verifyInitialState = async (page) => {
    const canvas = page.locator('#deck-container canvas');
    await expect(canvas).toHaveScreenshot('cord19-initial-state.png');
  };

  test('zoom functionality', { tag: '@slow' }, async ({ page }) => {
    test.slow();
    await verifyInitialState(page);
    const canvas = page.locator('#deck-container canvas');

    // Perform zoom
    await canvas.hover();
    await page.mouse.wheel(0, -100);

    await page.waitForLoadState('networkidle');
    await expect(canvas).toHaveScreenshot('cord19-after-zoom.png');
  });

  test('search functionality', { tag: '@slow' }, async ({ page }) => {
    await verifyInitialState(page);
    const canvas = page.locator('#deck-container canvas');

    await page.locator('#text-search').fill('covid');

    await page.waitForLoadState('networkidle');
    await expect(canvas).toHaveScreenshot('cord19-after-search-covid.png');
  });

  test('pan functionality', { tag: '@slow' }, async ({ page }) => {
    test.slow();
    await verifyInitialState(page);
    const canvas = page.locator('#deck-container canvas');

    const startX = 640;  // Half of 1280 (middle of canvas)
    const startY = 360;  // Half of 720 (middle of canvas)

    await canvas.hover();
    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX + 300, startY, { steps: 5 });
    await page.mouse.up();

    await page.waitForLoadState('networkidle');
    await expect(canvas).toHaveScreenshot('cord19-after-pan.png');
  });
});