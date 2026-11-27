import { test, expect, Page } from '@playwright/test';

// Live re-embedding (ReembedWidget) against the synthetic re-embed test server
// (reembed_test_server.py), on the CPU engine. Functional checks only -- no
// screenshot baselines. CI starts the server and sets REEMBED_TEST_URL; without
// it the tests look for a server on the default port and are skipped if there
// is none.

const SERVER = process.env.REEMBED_TEST_URL || 'http://127.0.0.1:8766/';

const state = (page: Page) =>
  page.evaluate(() => {
    const ctl = (window as any).datamap.widgets.reembed.controller;
    const deck = (window as any).datamap.deckgl;
    return {
      mode: ctl.mode,
      depth: ctl.depth,
      phase: ctl.status.phase,
      error: ctl.status.error,
      epoch: ctl.status.epoch,
      nEpochs: ctl.status.nEpochs,
      selection: ctl.selectionCount,
      shownN: ctl.current() ? ctl.current().n : null,
      sampled: !!ctl.status.sampleTiming,
      allVisible: !ctl.alpha || Array.from(ctl.alpha as Float32Array).every((a) => a > 0.99),
      layers: deck.props.layers.map((l: any) => l.id) as string[],
      filtered: !!deck.props.layerFilter,
    };
  });

// Lasso the points nearest a point of the map (a quarter of them), as the lasso tool would.
const lassoCluster = (page: Page) =>
  page.evaluate(() => {
    const dm = (window as any).datamap;
    const pos = dm.getPoints().positions;
    const n = pos.length / 2;
    const cx = pos[0], cy = pos[1];
    const d2 = Array.from({ length: n }, (_, i) => (pos[2 * i] - cx) ** 2 + (pos[2 * i + 1] - cy) ** 2).sort((a, b) => a - b);
    const r = Math.sqrt(d2[Math.floor(n / 4)]);
    const polygon = Array.from({ length: 48 }, (_, k) => ({
      x: cx + r * Math.cos((2 * Math.PI * k) / 48),
      y: cy + r * Math.sin((2 * Math.PI * k) / 48),
    }));
    dm.lassoSelector.onLassoComplete(polygon);
  });

const reembed = async (page: Page) => {
  await page.locator('.reembed-go').click();
  await page.waitForFunction(() => {
    const ctl = (window as any).datamap.widgets.reembed.controller;
    return (ctl.status.phase === 'done' && ctl.mode === 'idle') || !!ctl.status.error;
  }, undefined, { timeout: 120_000, polling: 250 });
};

const back = async (page: Page) => {
  await page.locator('.reembed-back').click();
  await page.waitForFunction(() => {
    const ctl = (window as any).datamap.widgets.reembed.controller;
    return ctl.depth === 0 && ctl.mode === 'idle' && !ctl.tr;
  }, undefined, { timeout: 30_000 });
};

test.describe('Live re-embedding', () => {
  let errors: string[] = [];

  test.beforeEach(async ({ page }, testInfo) => {
    test.skip(testInfo.project.name.includes('mobile'), 'desktop browsers only');
    testInfo.setTimeout(testInfo.timeout + 300_000);
    const reachable = await fetch(new URL('api/info', SERVER)).then((r) => r.ok, () => false);
    if (!reachable) {
      if (process.env.REEMBED_TEST_URL) throw new Error(`no re-embed test server at ${SERVER}`);
      test.skip(true, 'start python datamapplot/interactive_tests/reembed_test_server.py to run these');
    }
    errors = [];
    // Headless browsers time out loading the map's web font; that is expected.
    const record = (text: string) => { if (!text.includes('did not load within')) errors.push(text); };
    page.on('pageerror', (e) => record(String(e)));
    page.on('console', (m) => { if (m.type() === 'error') record(m.text()); });
    await page.goto(SERVER);
    // The widget is ready once it has found the server and the server has warmed up.
    await page.waitForFunction(() => {
      const ctl = (window as any).datamap?.widgets?.reembed?.controller;
      return !!ctl && ctl.server?.stage === 'ready';
    }, undefined, { timeout: 240_000, polling: 500 });
  });

  test.afterEach(async () => {
    expect(errors).toEqual([]);
  });

  test('re-embeds a lasso selection and goes back', async ({ page }) => {
    const before = await state(page);
    await lassoCluster(page);
    const selected = (await state(page)).selection;
    expect(selected).toBeGreaterThan(100);

    await reembed(page);
    const s = await state(page);
    expect(s.error).toBeNull();
    expect(s.depth).toBe(1);
    expect(s.shownN).toBe(selected);
    expect(s.nEpochs).toBeGreaterThan(0);
    expect(s.epoch).toBe(s.nEpochs);
    expect(s.layers).toContain('reembed-active');
    expect(s.filtered).toBe(true);

    await back(page);
    const after = await state(page);
    expect(after.layers).toEqual(before.layers);
    expect(after.filtered).toBe(false);
  });

  test('re-embeds scattered search results, starting from a sample', async ({ page }) => {
    // Sample first, as for selections too large to optimize at once.
    await page.evaluate(() => {
      const cfg = (window as any).datamap.widgets.reembed.controller.cfg;
      Object.assign(cfg, { subsample_threshold: 300, sample_size: 200, refine_epochs: 40 });
    });
    await page.locator('#text-search').fill('gamma');
    await page.waitForFunction(() => (window as any).datamap.widgets.reembed.controller.selectionCount > 300,
      undefined, { timeout: 10_000 });
    const selected = (await state(page)).selection;

    await reembed(page);
    const s = await state(page);
    expect(s.error).toBeNull();
    expect(s.shownN).toBe(selected);
    expect(s.sampled).toBe(true);
    expect(s.nEpochs).toBe(40);
    expect(s.epoch).toBe(40);
    expect(s.allVisible).toBe(true);
    // The search stays active: everything shown is selected, so there is nothing more to re-embed.
    expect(s.selection).toBe(0);
    await expect(page.locator('.reembed-go')).toBeDisabled();

    await back(page);
    await page.waitForFunction((n) => (window as any).datamap.widgets.reembed.controller.selectionCount === n,
      selected, { timeout: 10_000 });
  });
});
