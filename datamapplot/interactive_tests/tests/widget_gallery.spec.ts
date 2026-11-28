import { test, expect, Page } from '@playwright/test';
import { waitForDeckGL } from '../utils/canvas';

// Every built-in widget on one map, in light (Roboto) and dark (Playfair
// Display) themes: pages built by widget_gallery.py (via the Python test
// suite). Desktop layouts only.

const WIDGETS = [
  'annotation', 'colormap-selector', 'd3histogram', 'layer-toggle', 'legend',
  'minimap', 'rest-search', 'selection-control', 'topic-tree',
];

// Lasso the tenth of the points nearest the first point, as the lasso tool would.
const lasso = (page: Page) =>
  page.evaluate(() => {
    const selector = (window as any).datamap.lassoSelector;
    const p = selector.points;
    const n = p.length / 2;
    const cx = p[0], cy = p[1];
    const d2 = Array.from({ length: n }, (_, i) => (p[2 * i] - cx) ** 2 + (p[2 * i + 1] - cy) ** 2)
      .sort((a, b) => a - b);
    const r = Math.sqrt(d2[Math.floor(n / 10)]);
    selector.onLassoComplete(Array.from({ length: 48 }, (_, k) => ({
      x: cx + r * Math.cos((2 * Math.PI * k) / 48),
      y: cy + r * Math.sin((2 * Math.PI * k) / 48),
    })));
  });

const openDrawer = async (page: Page, side: string) => {
  await page.evaluate((s) => {
    const drawers = (window as any).drawerManager;
    drawers.closeAll();
    drawers.openDrawer(s);
  }, side);
  await page.waitForTimeout(800); // slide-in transition
};

for (const theme of ['light', 'dark']) {
  test.describe(`Widget gallery (${theme})`, () => {
    test.use({ viewport: { width: 1600, height: 1000 } });
    let errors: string[] = [];

    test.beforeEach(async ({ page }, testInfo) => {
      test.skip(testInfo.project.name.includes('mobile'), 'desktop layout only');
      testInfo.setTimeout(testInfo.timeout + 240_000);
      errors = [];
      // Headless browsers may time out loading the web font; that is expected.
      const record = (text: string) => { if (!text.includes('did not load within')) errors.push(text); };
      page.on('pageerror', (e) => record(String(e)));
      page.on('console', (m) => { if (m.type() === 'error') record(m.text()); });

      const response = await page.goto(`http://localhost:8000/widget_gallery_${theme}.html`, { timeout: 60_000 });
      expect(response.status()).toBe(200);
      await page.waitForSelector('#loading', { state: 'hidden', timeout: 180_000 });
      await page.waitForFunction(() => {
        const dm = (window as any).datamap;
        return !!dm && !!dm.labelData && !!dm.colorData && !!dm.lassoSelector;
      }, undefined, { timeout: 180_000 });
      await waitForDeckGL(page, testInfo);
      await page.evaluate(() => document.fonts.ready);
      await page.waitForTimeout(1000);
    });

    test.afterEach(async () => {
      expect(errors).toEqual([]);
    });

    test('widgets look consistent', async ({ page }) => {
      const ids = await page.evaluate(() => Object.keys((window as any).datamap.widgets || {}));
      expect(ids).toEqual(expect.arrayContaining(WIDGETS));
      // The logo sits in its corner stack, on screen and not covered by other widgets.
      const logoOnTop = await page.evaluate(() => {
        const img = document.querySelector('#logo-container img') as HTMLElement;
        const r = img.getBoundingClientRect();
        return r.bottom <= innerHeight && document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2) === img;
      });
      expect(logoOnTop).toBe(true);

      await expect(page).toHaveScreenshot(`widget-gallery-${theme}.png`);

      await page.locator('#colormap-selector-container .color-map-selected').first().click();
      await expect(page).toHaveScreenshot(`widget-gallery-${theme}-colormaps.png`);
      await page.locator('.color-map-option', { hasText: 'Field' }).first().click();
      await page.waitForTimeout(500);
      await expect(page).toHaveScreenshot(`widget-gallery-${theme}-legend.png`);

      await lasso(page);
      await openDrawer(page, 'left');
      await expect(page).toHaveScreenshot(`widget-gallery-${theme}-drawer-left.png`);
      await openDrawer(page, 'right');
      // The sample of selected points is random.
      await expect(page).toHaveScreenshot(`widget-gallery-${theme}-drawer-right.png`, {
        mask: [page.locator('#selection-display')],
      });
    });
  });
}
