import { test, expect } from '@playwright/test';

test.describe('Cord19 Canvas Tests', () => {
  test.beforeEach(async ({ page }, testInfo) => {
    // Extend timeout for all tests running this hook by 6 minutes.
    testInfo.setTimeout(testInfo.timeout + 360_000);
    // Set consistent viewport size
    await page.setViewportSize({ width: 1280, height: 720 });

    // Load the page
    const response = await page.goto('http://localhost:8000/cord19.html', { timeout: 60_000 });
    expect(response.status()).toBe(200);

    // Wait for loading
    console.log('Waiting for everything to load...');
    await Promise.all([
      page.waitForSelector('#loading', { state: 'hidden', timeout: 180_000 }),
      page.waitForSelector('#progress-container', { state: 'hidden', timeout: 180_000 }),
      page.waitForSelector('#deck-container canvas', { state: 'visible', timeout: 180_000 }),
      page.waitForLoadState('networkidle')
    ]);
  });

  const verifyInitialState = async (page) => {
    const canvas = page.locator('#deck-container canvas');
    await expect(canvas).toHaveScreenshot('cord19-initial-state.png');
  };

  const waitForCanvas = async (page) => {
    console.log('Waiting for canvas...');
    const canvas = page.locator('#deck-container canvas');
    await canvas.waitFor({ state: 'visible', timeout: 180_000 });
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000); // Additional wait for stability
    console.log('Canvas ready');
    return canvas;
  };

  test('zoom functionality', { tag: '@slow' }, async ({ page }, testInfo) => {
    if (testInfo.project.name === 'Mobile Safari') {
      test.skip('page.mouse.wheel is not supported on mobile webkit');
    } else {
      test.slow();
      await verifyInitialState(page);
      const canvas = page.locator('#deck-container canvas');

      // Perform zoom
      await canvas.hover();
      await page.mouse.wheel(0, -100);
      await waitForCanvas(page);
      await expect(canvas).toHaveScreenshot('cord19-after-zoom.png', {
        timeout: 180_000
      });
    }
  });

  test('search functionality', { tag: '@slow' }, async ({ page }) => {
    await verifyInitialState(page);
    const canvas = page.locator('#deck-container canvas');

    await page.locator('#text-search').fill('covid');

    await waitForCanvas(page);
    await expect(canvas).toHaveScreenshot('cord19-after-search-covid.png', {
      timeout: 180_000
    });
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

    await waitForCanvas(page);
    await expect(canvas).toHaveScreenshot('cord19-after-pan.png', {
      timeout: 180_000
    });
  });
});