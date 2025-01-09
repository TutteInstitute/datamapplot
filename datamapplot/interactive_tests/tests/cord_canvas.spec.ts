import { test, expect } from '@playwright/test';

test.describe('Cord19 Canvas Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Set consistent viewport size
    await page.setViewportSize({ width: 1280, height: 720 });
    
    await page.goto('http://localhost:8000/cord19.html');
    
    // Wait for loading
    await page.waitForSelector('#loading', { state: 'hidden' });
    await page.waitForTimeout(500);
    await page.waitForSelector('#progress-container', { state: 'hidden' });
  });

  const verifyInitialState = async (page) => {
    const canvas = page.locator('#deck-container canvas');
    await expect(canvas).toHaveScreenshot('initial-state.png');
  };

  test('zoom functionality', async ({ page }) => {
    await verifyInitialState(page);
    const canvas = page.locator('#deck-container canvas');
    
    // Perform zoom
    await canvas.hover();
    await page.mouse.wheel(0, -100);
    
    await page.waitForTimeout(500);
    await expect(canvas).toHaveScreenshot('after-zoom.png');
  });

  test('search functionality', async ({ page }) => {
    await verifyInitialState(page);
    const canvas = page.locator('#deck-container canvas');
    
    await page.locator('#text-search').fill('covid');
    
    await page.waitForTimeout(500);
    
    await expect(canvas).toHaveScreenshot('after-search-covid.png');
  });

  test('pan functionality', async ({ page }) => {
    await verifyInitialState(page);
    const canvas = page.locator('#deck-container canvas');
    
    const startX = 640;  // Half of 1280 (middle of canvas)
    const startY = 360;  // Half of 720 (middle of canvas)

    await canvas.hover();
    await page.mouse.move(startX, startY);
    await page.mouse.down();
    await page.mouse.move(startX + 300, startY, { steps: 10 }); // Added steps for smoother movement
    await page.mouse.up();
    
    await page.waitForTimeout(500);
    await expect(canvas).toHaveScreenshot('after-pan.png');
  });
});