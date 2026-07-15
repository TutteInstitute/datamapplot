import { test, expect, Page } from '@playwright/test';
import { waitForDeckGL, waitForCanvas } from '../utils/canvas';

// Tests for the touch tap-to-inspect card: tapping a point shows its hover
// content in a bottom-sheet card, and the arxiv_ml fixture's on_click is
// exposed as the card's action button instead of firing on the tap itself.
// DOM assertions only -- no screenshot baselines. Not tagged @slow so the
// touch-capable mobile projects run these tests.

const CARD = '.tap-inspect-card';

// The fixtures ship no <meta name="viewport">, so mobile WebKit lays the page
// out at ~980px and scales it down to the 844px visual viewport. Playwright
// dispatches touch taps in visual-viewport coordinates while all our geometry
// (deck.gl projections, getBoundingClientRect) is in layout coordinates, so
// taps land short of their target. Calibrate the ratio empirically with one
// throwaway tap: it is exactly 1 on Chromium, and will become 1 on WebKit too
// once the output emits a viewport meta tag.
const calibrateTouch = async (page: Page) => {
  await page.evaluate(() => {
    (window as any).__tapCal = new Promise((resolve) => {
      const handler = (e: TouchEvent) => {
        document.removeEventListener('touchstart', handler, true);
        resolve({ x: e.touches[0].clientX, y: e.touches[0].clientY });
      };
      document.addEventListener('touchstart', handler, true);
    });
  });
  await page.touchscreen.tap(100, 100);
  const landed = await page.evaluate(() => (window as any).__tapCal);
  // The calibration tap may have opened the card; reset state.
  await page.evaluate(() => (window as any).tapToInspect?.hide());
  await page.waitForTimeout(600); // let the self-close guard window expire
  return { sx: (landed as any).x / 100, sy: (landed as any).y / 100 };
};

type TouchCal = { sx: number; sy: number };

const tapAt = async (page: Page, cal: TouchCal, x: number, y: number) =>
  page.touchscreen.tap(x / cal.sx, y / cal.sy);

const tapElement = async (page: Page, cal: TouchCal, selector: string) => {
  const rect = await page.evaluate((sel) => {
    const el = document.querySelector(sel);
    if (!el) return null;
    const b = el.getBoundingClientRect();
    return { x: b.x + b.width / 2, y: b.y + b.height / 2 };
  }, selector);
  expect(rect, `element not found: ${selector}`).toBeTruthy();
  await tapAt(page, cal, rect!.x, rect!.y);
};

// Title of the one test that runs on desktop projects; every other test in
// this suite is touch-only. Used to skip mismatched project/test pairs in
// beforeEach, before paying for the fixture load. The in-test skip guards
// stay as the source of truth if titles drift.
const DESKTOP_TEST = 'mouse hover and click are unchanged on desktop';

test.describe('Tap-to-inspect', () => {
  test.beforeEach(async ({ page }, testInfo) => {
    const isMobile = testInfo.project.name.includes('mobile');
    if (isMobile) {
      test.skip(testInfo.title === DESKTOP_TEST, 'desktop-only regression check');
    } else {
      test.skip(testInfo.title !== DESKTOP_TEST, 'touch-only behavior');
    }

    // Extend timeout for all tests running this hook by 4 minutes.
    testInfo.setTimeout(testInfo.timeout + 240_000);

    const response = await page.goto('http://localhost:8000/arxiv_ml.html', { timeout: 60_000 });
    expect(response.status()).toBe(200);

    await Promise.all([
      page.waitForSelector('#loading', { state: 'hidden', timeout: 180_000 }),
      page.waitForSelector('#progress-container', { state: 'hidden', timeout: 180_000 }),
    ]);
    await waitForDeckGL(page, testInfo);

    // Tap targets need the point metadata (hover text) to be loaded.
    // Interval polling: the default rAF polling stalls forever on headless
    // Firefox in CI, which throttles rAF for occluded pages once idle.
    await page.waitForFunction(
      () => (window as any).datamap?.metaData?.hover_text?.length > 0,
      undefined,
      { timeout: 180_000, polling: 100 },
    );

    // deck.gl creates its view manager on the first animation frame, which
    // can lag the data-loaded signal on slow (software-GL) CI machines.
    await page.waitForFunction(
      () => {
        // deck.getViewports() asserts while the view manager is still null;
        // treat that (and any other init-time throw) as "not ready yet".
        try {
          const dg = (window as any).datamap?.deckgl;
          const vp = dg?.viewManager?.getViewports?.()[0] || dg?.getViewports?.()[0];
          return !!vp && vp.width > 0;
        } catch (e) {
          return false;
        }
      },
      undefined,
      { timeout: 180_000, polling: 100 },
    );

    // Zoom in around the data center so individual points are several pixels
    // wide and reliably pickable at their projected positions.
    await page.evaluate(() => {
      const dm = (window as any).datamap;
      const vp = dm.deckgl.viewManager?.getViewports?.()[0] || dm.deckgl.getViewports?.()[0];
      const viewState = {
        latitude: vp.latitude,
        longitude: vp.longitude,
        zoom: vp.zoom + 4,
        transitionDuration: 0,
      };
      dm.deckgl.setProps({ initialViewState: viewState });
      dm.notifyViewStateChange(viewState);
    });
    await waitForCanvas(page);
  });

  // Find a point that deck.gl confirms as pickable at its projected screen
  // position, plus an empty spot where a pick returns nothing.
  const findTapTargets = async (page: Page) => {
    const targets = await page.evaluate(() => {
      const dm = (window as any).datamap;
      const vp = dm.deckgl.viewManager?.getViewports?.()[0] || dm.deckgl.getViewports?.()[0];
      const cx = vp.width / 2;
      const cy = vp.height / 2;

      const n = dm.pointData.x.length;
      const step = Math.max(1, Math.floor(n / 20000));
      const projected: Array<[number, number, number]> = [];
      for (let i = 0; i < n; i += step) {
        const [px, py] = vp.project([dm.pointData.x[i], dm.pointData.y[i]]);
        if (px >= 5 && px <= vp.width - 5 && py >= 5 && py <= vp.height - 5) {
          projected.push([px, py, i]);
        }
      }

      // Point target: nearest the viewport center that actually picks.
      const byCenterDistance = [...projected].sort(
        (a, b) =>
          (a[0] - cx) ** 2 + (a[1] - cy) ** 2 -
          ((b[0] - cx) ** 2 + (b[1] - cy) ** 2)
      );
      let point = null;
      for (const [px, py] of byCenterDistance.slice(0, 200)) {
        const pick = dm.deckgl.pickObject({ x: px, y: py, radius: 1 });
        if (pick && pick.picked && pick.index >= 0) {
          point = {
            x: px,
            y: py,
            index: pick.index,
            hoverText: dm.metaData.hover_text[pick.index],
          };
          break;
        }
      }

      // Empty spot: the grid cell in the mid/lower canvas band with the
      // largest clearance from any projected point, verified by picking.
      const candidates: Array<[number, number, number]> = [];
      for (let gy = Math.round(vp.height * 0.3); gy < vp.height * 0.9; gy += 24) {
        for (let gx = 12; gx < vp.width - 12; gx += 24) {
          let minD = Infinity;
          for (const [px, py] of projected) {
            const d = (px - gx) ** 2 + (py - gy) ** 2;
            if (d < minD) {
              minD = d;
              if (minD < 1600) break;
            }
          }
          if (minD >= 1600) candidates.push([minD, gx, gy]);
        }
      }
      candidates.sort((a, b) => b[0] - a[0]);
      let empty = null;
      for (const [, gx, gy] of candidates.slice(0, 5)) {
        const pick = dm.deckgl.pickObject({ x: gx, y: gy, radius: 8 });
        if (!pick || !pick.picked) {
          empty = { x: gx, y: gy };
          break;
        }
      }

      return { point, empty };
    });
    expect(targets.point, 'no pickable point found').toBeTruthy();
    expect(targets.empty, 'no empty spot found').toBeTruthy();
    return targets as {
      point: { x: number; y: number; index: number; hoverText: string };
      empty: { x: number; y: number };
    };
  };

  test('tap on a point shows the card and suppresses on_click', async ({ page }, testInfo) => {
    test.skip(!testInfo.project.name.includes('mobile'), 'touch-only behavior');
    const cal = await calibrateTouch(page);
    const { point } = await findTapTargets(page);

    let popupOpened = false;
    page.on('popup', () => { popupOpened = true; });

    await tapAt(page, cal, point.x, point.y);

    const card = page.locator(CARD);
    await expect(card).toBeVisible();
    await expect(card.locator('.tap-inspect-card-content')).toContainText(
      point.hoverText.slice(0, 30)
    );
    await expect(card.locator('.tap-inspect-action')).toBeVisible();
    await expect(card.locator('.tap-inspect-action')).toHaveText('Open');

    await page.waitForTimeout(500);
    expect(popupOpened, 'on_click must not fire on a bare tap').toBe(false);
  });

  test('tapping empty space dismisses the card', async ({ page }, testInfo) => {
    test.skip(!testInfo.project.name.includes('mobile'), 'touch-only behavior');
    const cal = await calibrateTouch(page);
    const { point, empty } = await findTapTargets(page);

    await tapAt(page, cal, point.x, point.y);
    const card = page.locator(CARD);
    await expect(card).toBeVisible();

    // Get past the self-close guard window before dismissing.
    await page.waitForTimeout(500);
    await tapAt(page, cal, empty.x, empty.y);
    await expect(card).toBeHidden();
  });

  test('close button dismisses the card and clears the highlight', async ({ page }, testInfo) => {
    test.skip(!testInfo.project.name.includes('mobile'), 'touch-only behavior');
    const cal = await calibrateTouch(page);
    const { point } = await findTapTargets(page);

    // Pixel-level check of deck.gl's point highlight around the tapped
    // point (compared at runtime -- no stored baselines). Scaled-viewport
    // WebKit makes clip coordinates unreliable, so mobile-chrome only.
    const checkPixels = testInfo.project.name === 'mobile-chrome';
    const clip = { x: point.x - 8, y: point.y - 8, width: 16, height: 16 };
    const pristine = checkPixels ? await page.screenshot({ clip }) : null;

    await tapAt(page, cal, point.x, point.y);
    const card = page.locator(CARD);
    await expect(card).toBeVisible();

    if (checkPixels) {
      await page.waitForTimeout(400);
      const highlighted = await page.screenshot({ clip });
      expect(highlighted.equals(pristine!), 'tap should highlight the point').toBe(false);

      await tapElement(page, cal, '.tap-inspect-close');
      await expect(card).toBeHidden();
      await page.waitForTimeout(400);
      const dismissed = await page.screenshot({ clip });
      expect(dismissed.equals(pristine!), 'dismissal should clear the highlight').toBe(true);
    } else {
      await tapElement(page, cal, '.tap-inspect-close');
      await expect(card).toBeHidden();
    }
  });

  test('action button triggers on_click', async ({ page }, testInfo) => {
    test.skip(
      testInfo.project.name !== 'mobile-chrome',
      'popup handling is only reliable on mobile-chrome'
    );
    const cal = await calibrateTouch(page);
    const { point } = await findTapTargets(page);

    await tapAt(page, cal, point.x, point.y);
    const card = page.locator(CARD);
    await expect(card).toBeVisible();

    const [popup] = await Promise.all([
      page.waitForEvent('popup', { timeout: 30_000 }),
      tapElement(page, cal, '.tap-inspect-action'),
    ]);
    expect(popup).toBeTruthy();
    await popup.close();
  });

  test('mouse hover and click are unchanged on desktop', async ({ page }, testInfo) => {
    test.skip(testInfo.project.name.includes('mobile'), 'desktop-only regression check');
    const { point } = await findTapTargets(page);

    await page.mouse.move(point.x - 30, point.y - 30);
    await page.mouse.move(point.x, point.y, { steps: 3 });

    const tooltip = page.locator('.deck-tooltip');
    await expect(tooltip).toBeVisible();
    await expect(tooltip).toContainText(point.hoverText.slice(0, 30));
    await expect(page.locator(CARD)).toBeHidden();

    // A mouse click still fires on_click directly (opens a popup) and does
    // not open the card.
    page.on('popup', (p) => { p.close().catch(() => {}); });
    await page.mouse.click(point.x, point.y);
    await page.waitForTimeout(500);
    await expect(page.locator(CARD)).toBeHidden();
  });
});
