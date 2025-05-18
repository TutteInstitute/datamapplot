import { Page } from '@playwright/test';

export const waitForDeckGL = async (page:Page, testInfo?:any) => {
  const canvas = page.locator('#deck-container canvas');
  await canvas.waitFor({ state: 'visible', timeout: 360_000 });

  const deckReady = await page.evaluate((projectName) => {
    const canvas = document.querySelector('#deck-container canvas');
    if (!canvas) return { ready: false, error: 'No canvas' };

    const gl = canvas.getContext('webgl2') || canvas.getContext('webgl');
    if (!gl) return { ready: false, error: 'No WebGL context' };

    const deckIsWorking = canvas.width > 0 && canvas.height > 0 && gl.drawingBufferWidth > 0;

    return {
      project: projectName,
      ready: deckIsWorking,
      dimensions: {
        width: canvas.width,
        height: canvas.height
      },
    //   debug: {
    //     deckExists: 'deck' in window,
    //     glSize: `${gl.drawingBufferWidth}x${gl.drawingBufferHeight}`,
    //     contextAttributes: !!gl.getContextAttributes(),
    //     extensions: !!gl.getSupportedExtensions()
    //   }
    };
  }, testInfo?.project.name);

  return deckReady;
};

export const waitForCanvas = async (page:Page) => {
  const canvas = page.locator('#deck-container canvas');
  await canvas.waitFor({ state: 'visible', timeout: 180_000 });
  await page.waitForLoadState('networkidle');
  await page.waitForTimeout(500); // Additional wait for stability
  const deckInfo = await waitForDeckGL(page);
//   console.debug({
//     ready: deckInfo.ready,
//     dimensions: deckInfo.dimensions,
//   });
  return canvas;
};