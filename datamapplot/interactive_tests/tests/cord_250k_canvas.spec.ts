import { test, expect } from '@playwright/test';
import { waitForDeckGL, waitForCanvas } from '../utils/canvas';


test.describe('Cord19 Canvas Tests', () => {
  test.beforeEach(async ({ page }, testInfo) => {
    // Extend timeout for all tests running this hook by 6 minutes.
    testInfo.setTimeout(testInfo.timeout + 360_000);

    const response = await page.goto('http://localhost:8000/cord19_250000.html', { timeout: 60_000 });
    expect(response.status()).toBe(200);

    console.log('Waiting for initial load...', testInfo.project.name);
    await Promise.all([
      page.waitForSelector('#loading', { state: 'hidden', timeout: 180_000 }),
      page.waitForSelector('#progress-container', { state: 'hidden', timeout: 180_000 }),
    ]);

    const deckReady = await waitForDeckGL(page, testInfo);
    console.debug('Deck.gl state:', deckReady);
  });

  const verifyInitialState = async (page) => {
    const canvas = await waitForCanvas(page);
    await expect(canvas).toHaveScreenshot('cord19-250k-initial-state.png', { timeout: 180_000 });
    return canvas;
  };

  test('zoom functionality', async ({ page }, testInfo) => {
    if (testInfo.project.name === 'mobile-safari') {
      test.skip('page.mouse.wheel is not supported on mobile webkit');
    } else {
      test.slow();
      const canvas = await verifyInitialState(page);

      // Handle hover/tap based on device
      const isMobile = testInfo.project.name.includes('mobile');
      if (isMobile) {
        await page.touchscreen.tap(100, 100);
      } else {
        await canvas.hover();
      }
      await page.mouse.wheel(0, -100);
      await waitForCanvas(page);
      await expect(canvas).toHaveScreenshot('cord19-250k-after-zoom.png', {
        timeout: 180_000
      });
    }
  });

  test('search functionality', async ({ page }) => {
    const canvas = await verifyInitialState(page);

    await page.locator('#text-search').fill('covid');

    await waitForCanvas(page);
    await expect(canvas).toHaveScreenshot('cord19-250k-after-search-covid.png', {
      timeout: 180_000
    });
  });

  test('pan functionality', async ({ page }, testInfo) => {
    test.slow();
    const canvas = await verifyInitialState(page);

    const size = await page.evaluate(() => {
      const canvasSelector = document.querySelector('#deck-container canvas');
      return { width: canvasSelector.width, height: canvasSelector.height };
    });
    const startX = 100;
    const startY =  360;
    const move = Math.min(size.width / 4, 300); // Move either quarter canvas width or 300px, whichever is smaller

    // Handle hover/tap based on device
    const isMobile = testInfo.project.name.includes('mobile');
    if (isMobile) {
      await page.touchscreen.tap(startX, startY);
    } else {
      await canvas.hover();
    }
    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX + move, startY, { steps: 5 });
    await page.mouse.up();
    await waitForCanvas(page);
    await expect(canvas).toHaveScreenshot('cord19-250k-after-pan.png', {
      timeout: 180_000
    });
  });
});