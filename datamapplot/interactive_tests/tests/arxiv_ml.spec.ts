import { test, expect } from '@playwright/test';

test.describe('Arxiv ML Canvas Tests', () => {
  test.beforeEach(async ({ page }, testInfo) => {
    // Extend timeout for all tests running this hook by 4 minutes.
    testInfo.setTimeout(testInfo.timeout + 240_000);

    // Add console listeners first
    // page.on('console', msg => {
    //   const type = msg.type();
    //   const text = msg.text();
    //   console.log(`Browser ${type}: ${text}`);
    // });

    const response = await page.goto('http://localhost:8000/arxiv_ml.html', { timeout: 60_000 });
    expect(response.status()).toBe(200);

    console.log('Waiting for initial load:', testInfo.project.name);
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

      console.debug('Deck.gl debug state:', deckReady);
      return canvas;
    };

    const canvas = await waitForDeckGL(page);

  //  // Patch deck.gl to log redraw calls
  //   const patchResult = await page.evaluate(() => {
  //     try {
  //       if (!window.deck?.Deck) {
  //         return { success: false, error: 'No deck.gl' };
  //       }

  //       const proto = window.deck.Deck.prototype;
  //       const origRedraw = proto.redraw;

  //       proto.redraw = function(...args) {
  //         console.log('Redraw called:', {
  //           hasViewState: !!this.viewState,
  //           viewState: this.viewState,
  //           timestamp: Date.now(),
  //           props: this.props
  //         });
  //         return origRedraw.apply(this, args);
  //       };

  //       return {
  //         success: true,
  //         method: 'redraw'
  //       };
  //     } catch (e) {
  //       return {
  //         success: false,
  //         error: e.toString()
  //       };
  //     }
  //   });
  //   console.log('Patch result:', patchResult);
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
        extensions: !!ctx.getSupportedExtensions()
      };
    });

    // console.debug(canvasInfo);
    return canvas;
  };

  const verifyInitialState = async (page) => {
    const canvas = await waitForCanvas(page);
    await expect(canvas).toHaveScreenshot('arxiv-ml-initial-state.png', { timeout: 180_000 });
    return canvas;
  };

  test('zoom functionality', async ({ page }, testInfo ) => {
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
    await expect(canvas).toHaveScreenshot('arxiv-ml-after-pan.png', {
      timeout: 180_000  // Explicit timeout for screenshot
    });
  });
});