import { test, expect } from '@playwright/test';

test.describe('Cord19 Canvas Tests', () => {
  test.beforeEach(async ({ page }, testInfo) => {
    // Extend timeout for all tests running this hook by 6 minutes.
    testInfo.setTimeout(testInfo.timeout + 360_000);

    const response = await page.goto('http://localhost:8000/cord19.html', { timeout: 60_000 });
    expect(response.status()).toBe(200);

    console.log('Waiting for initial load...');
    await Promise.all([
      page.waitForSelector('#loading', { state: 'hidden', timeout: 180_000 }),
      page.waitForSelector('#progress-container', { state: 'hidden', timeout: 180_000 }),
    ]);

    const waitForDeckGL = async (page) => {
      console.log('Waiting for deck.gl...');

      const canvas = page.locator('#deck-container canvas');
      await canvas.waitFor({ state: 'visible', timeout: 180_000 });

      const deckReady = await page.evaluate(() => {
        const canvas = document.querySelector('#deck-container canvas');
        if (!canvas) return { ready: false, error: 'No canvas' };

        const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
        if (!gl) return { ready: false, error: 'No WebGL context' };

        // Check if deck is initialized without window assignment
        const deckIsWorking = canvas.width > 0 && canvas.height > 0 && gl.drawingBufferWidth > 0;

        return {
          ready: deckIsWorking,
          dimensions: {
            width: canvas.width,
            height: canvas.height
          },
          debug: {
            deckExists: 'deck' in window,
            canvasSize: `${canvas.width}x${canvas.height}`,
            glSize: `${gl.drawingBufferWidth}x${gl.drawingBufferHeight}`
          }
        };
      });

      console.log('Deck.gl debug state:', deckReady);
      return canvas;
    };

    const canvas = await waitForDeckGL(page);
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
      if (canvasSelector.width === 0 || canvasSelector.height === 0 || !canvasSelector) {
          console.log('Try redrawing');
          window.dispatchEvent(new Event('resize'));
          window.dispatchEvent(new Event('redraw'));
        }

      if (!canvasSelector) return null;

      const ctx = canvasSelector.getContext('webgl2') || canvasSelector.getContext('webgl');
      if (!ctx) return {
        width: canvasSelector.width,
        height: canvasSelector.height,
        error: 'No WebGL context available' };

      return {
        width: canvasSelector.width,
        height: canvasSelector.height,
        contextAttributes: !!ctx.getContextAttributes(),
        // extensions: ctx.getSupportedExtensions()
      };
    });

    console.log(canvasInfo);
    return canvas;
  };

  const verifyInitialState = async (page) => {
    const canvas = await waitForCanvas(page);
    await expect(canvas).toHaveScreenshot('cord19-initial-state.png');
    return canvas;
  };

  test('zoom functionality', { tag: '@slow' }, async ({ page }, testInfo) => {
    if (testInfo.project.name === 'Mobile Safari') {
      test.skip('page.mouse.wheel is not supported on mobile webkit');
    } else {
      test.slow();
      const canvas = await verifyInitialState(page);

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
    const canvas = await verifyInitialState(page);

    await page.locator('#text-search').fill('covid');

    await waitForCanvas(page);
    await expect(canvas).toHaveScreenshot('cord19-after-search-covid.png', {
      timeout: 180_000
    });
  });

  test('pan functionality', { tag: '@slow' }, async ({ page }) => {
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
    await expect(canvas).toHaveScreenshot('cord19-after-pan.png', {
      timeout: 180_000
    });
  });
});