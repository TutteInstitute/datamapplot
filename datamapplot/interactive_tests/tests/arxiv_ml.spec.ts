import { test, expect } from '@playwright/test';

test.describe('Arxiv ML Canvas Tests', () => {
  test.beforeEach(async ({ page }, testInfo) => {
    // Extend timeout for all tests running this hook by 4 minutes.
    testInfo.setTimeout(testInfo.timeout + 240_000);

    const response = await page.goto('http://localhost:8000/arxiv_ml.html', { timeout: 60_000 });
    expect(response.status()).toBe(200);

    console.log('Waiting for initial load...');
    await Promise.all([
      page.waitForSelector('#loading', { state: 'hidden', timeout: 180_000 }),
      page.waitForSelector('#progress-container', { state: 'hidden', timeout: 180_000 }),
    ]);
  });


  const waitForCanvas = async (page) => {
    console.log('Waiting for canvas...');
    const canvas = page.locator('#deck-container canvas');
    await canvas.waitFor({ state: 'visible', timeout: 180_000 });
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(500); // Additional wait for stability

    // Evaluate inside the browser context to access canvas properties
    const canvasInfo = await page.evaluate(() => {
      const canvasSelector = document.querySelector('#deck-container canvas');
      let msg = "No redraw"
      if (canvasSelector.width === 0 || canvasSelector.height === 0 || !canvasSelector) {
        if (window.deckInstance) {
          window.deckInstance.redraw(true);
        }
        window.dispatchEvent(new Event('resize'));
        window.dispatchEvent(new Event('redraw'));
        msg = "Redraw"
      }

      if (!canvasSelector) return null;

      const ctx = canvasSelector.getContext('webgl2') || canvasSelector.getContext('webgl');
      if (!ctx) return { width: canvasSelector.width, height: canvasSelector.height, error: 'No WebGL context available' };

      return {
        message: msg,
        width: canvasSelector.width,
        height: canvasSelector.height,
        contextAttributes: ctx.getContextAttributes(),
        // extensions: ctx.getSupportedExtensions()
      };
    });

    console.log(canvasInfo);
    console.log('Canvas ready');
    return canvas;
  };

  const verifyInitialState = async (page) => {
    const canvas = await waitForCanvas(page);
    await expect(canvas).toHaveScreenshot('arxiv-ml-initial-state.png');
    return canvas;
  };

  test('zoom functionality', async ({ page }, testInfo ) => {
    if (testInfo.project.name === 'Mobile Safari') {
      test.skip('page.mouse.wheel is not supported on mobile webkit');
    } else {
      test.slow();
      const canvas = await verifyInitialState(page);

      // Perform zoom
      await canvas.hover();
      await page.mouse.wheel(0, -100);

      await waitForCanvas(page);
      await expect(canvas).toHaveScreenshot('arxiv-ml-after-zoom.png', {
        timeout: 180_000  // Explicit timeout for screenshot
      });
    }
  });

  test('search functionality', async ({ page }) => {
    const canvas = await verifyInitialState(page);

    await page.locator('#text-search').fill('nlp');

    await waitForCanvas(page);
    await expect(canvas).toHaveScreenshot('arxiv-ml-after-search-nlp.png');
  });

  test('pan functionality', async ({ page }) => {
    test.slow();
    const canvas = await verifyInitialState(page);

    const startX = 640;  // Half of 1280 (middle of canvas)
    const startY = 360;  // Half of 720 (middle of canvas)

    await canvas.hover();
    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX + 300, startY, { steps: 5 });
    await page.mouse.up();

    await waitForCanvas(page);
    await expect(canvas).toHaveScreenshot('arxiv-ml-after-pan.png', {
      timeout: 180_000  // Explicit timeout for screenshot
    });
  });
});