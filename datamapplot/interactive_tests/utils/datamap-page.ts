import { Page, Locator, expect } from '@playwright/test';
import { waitForDeckGL, waitForCanvas } from './canvas';

/**
 * Page Object for DataMapPlot interactive figures.
 * Provides a high-level API for interacting with data map visualizations.
 */
export class DataMapPage {
    readonly page: Page;
    readonly baseUrl: string;

    constructor(page: Page, baseUrl: string = 'http://localhost:8000') {
        this.page = page;
        this.baseUrl = baseUrl;
    }

    /**
     * Navigate to an HTML file and wait for it to load.
     */
    async goto(htmlFile: string, options?: { timeout?: number }): Promise<void> {
        const timeout = options?.timeout ?? 60_000;
        const response = await this.page.goto(`${this.baseUrl}/${htmlFile}`, { timeout });
        expect(response?.status()).toBe(200);
    }

    /**
     * Wait for the data map to be fully loaded and ready for interaction.
     * This waits for loading indicators to disappear and DeckGL to initialize.
     */
    async waitForReady(testInfo?: any): Promise<void> {
        // Wait for loading indicators to disappear
        await Promise.all([
            this.page.waitForSelector('#loading', { state: 'hidden', timeout: 180_000 }).catch(() => { }),
            this.page.waitForSelector('#progress-container', { state: 'hidden', timeout: 180_000 }).catch(() => { }),
        ]);

        // Wait for DeckGL to be ready
        await waitForDeckGL(this.page, testInfo);
    }

    /**
     * Get the DeckGL canvas element.
     */
    getCanvas(): Locator {
        return this.page.locator('#deck-container canvas');
    }

    /**
     * Wait for the canvas to be stable (after interactions).
     */
    async waitForCanvasStable(): Promise<Locator> {
        return await waitForCanvas(this.page);
    }

    /**
     * Perform a zoom interaction on the canvas.
     * @param delta - Positive values zoom out, negative values zoom in
     * @param position - Optional x,y position to zoom at (defaults to center)
     */
    async zoom(delta: number, position?: { x: number; y: number }): Promise<void> {
        const canvas = this.getCanvas();

        if (position) {
            await this.page.mouse.move(position.x, position.y);
        } else {
            await canvas.hover();
        }

        await this.page.mouse.wheel(0, delta);
        await this.waitForCanvasStable();
    }

    /**
     * Perform a pan interaction on the canvas.
     */
    async pan(startX: number, startY: number, endX: number, endY: number, options?: { steps?: number }): Promise<void> {
        const steps = options?.steps ?? 5;

        await this.page.mouse.move(startX, startY);
        await this.page.mouse.down();
        await this.page.mouse.move(endX, endY, { steps });
        await this.page.mouse.up();
        await this.waitForCanvasStable();
    }

    /**
     * Perform a tap interaction (for mobile).
     */
    async tap(x: number, y: number): Promise<void> {
        await this.page.touchscreen.tap(x, y);
    }

    // ==================== Search ====================

    /**
     * Get the search input element.
     */
    getSearchInput(): Locator {
        return this.page.locator('#text-search');
    }

    /**
     * Check if search is enabled on this data map.
     */
    async hasSearch(): Promise<boolean> {
        return await this.getSearchInput().isVisible().catch(() => false);
    }

    /**
     * Enter a search query.
     */
    async search(query: string): Promise<void> {
        const searchInput = this.getSearchInput();
        await searchInput.fill(query);
        await this.waitForCanvasStable();
    }

    /**
     * Clear the search input.
     */
    async clearSearch(): Promise<void> {
        const searchInput = this.getSearchInput();
        await searchInput.clear();
        await this.waitForCanvasStable();
    }

    // ==================== Tooltip ====================

    /**
     * Get the tooltip element.
     */
    getTooltip(): Locator {
        return this.page.locator('#tooltip');
    }

    /**
     * Check if tooltip is currently visible.
     */
    async isTooltipVisible(): Promise<boolean> {
        const tooltip = this.getTooltip();
        return await tooltip.isVisible().catch(() => false);
    }

    /**
     * Get the current tooltip text content.
     */
    async getTooltipText(): Promise<string> {
        const tooltip = this.getTooltip();
        return await tooltip.textContent() ?? '';
    }

    /**
     * Hover over a specific point on the canvas to trigger tooltip.
     */
    async hoverAt(x: number, y: number): Promise<void> {
        await this.page.mouse.move(x, y);
        // Small delay to allow tooltip to appear
        await this.page.waitForTimeout(200);
    }

    // ==================== Selection ====================

    /**
     * Get the selection container element.
     */
    getSelectionContainer(): Locator {
        return this.page.locator('#selection-container');
    }

    /**
     * Check if selection is enabled on this data map.
     */
    async hasSelection(): Promise<boolean> {
        // Check if lasso selection is available by looking for selection-related elements
        return await this.getSelectionContainer().isVisible().catch(() => false);
    }

    /**
     * Perform a lasso selection by drawing a path.
     * @param points - Array of {x, y} coordinates defining the lasso path
     * @param modifier - Key to hold during selection (e.g., 'Shift')
     */
    async lassoSelect(points: Array<{ x: number; y: number }>, modifier: string = 'Shift'): Promise<void> {
        if (points.length < 2) return;

        await this.page.keyboard.down(modifier);

        await this.page.mouse.move(points[0].x, points[0].y);
        await this.page.mouse.down();

        for (let i = 1; i < points.length; i++) {
            await this.page.mouse.move(points[i].x, points[i].y, { steps: 3 });
        }

        await this.page.mouse.up();
        await this.page.keyboard.up(modifier);

        await this.waitForCanvasStable();
    }

    /**
     * Click the resample button in the selection container.
     */
    async clickResample(): Promise<void> {
        await this.page.locator('.resample-button').click();
    }

    /**
     * Click the clear selection button.
     */
    async clickClearSelection(): Promise<void> {
        await this.page.locator('.clear-selection-button').click();
        await this.waitForCanvasStable();
    }

    // ==================== Histogram ====================

    /**
     * Get the histogram container element.
     */
    getHistogram(): Locator {
        return this.page.locator('#histogram-container');
    }

    /**
     * Check if histogram is enabled on this data map.
     */
    async hasHistogram(): Promise<boolean> {
        return await this.getHistogram().isVisible().catch(() => false);
    }

    /**
     * Perform a brush selection on the histogram.
     */
    async brushHistogram(startX: number, endX: number): Promise<void> {
        const histogram = this.getHistogram();
        const box = await histogram.boundingBox();
        if (!box) return;

        const y = box.y + box.height / 2;

        await this.page.mouse.move(box.x + startX, y);
        await this.page.mouse.down();
        await this.page.mouse.move(box.x + endX, y, { steps: 5 });
        await this.page.mouse.up();

        await this.waitForCanvasStable();
    }

    // ==================== Topic Tree ====================

    /**
     * Get the topic tree container element.
     */
    getTopicTree(): Locator {
        return this.page.locator('#topic-tree-container');
    }

    /**
     * Check if topic tree is enabled on this data map.
     */
    async hasTopicTree(): Promise<boolean> {
        return await this.getTopicTree().isVisible().catch(() => false);
    }

    /**
     * Click on a topic in the topic tree.
     */
    async clickTopic(topicText: string): Promise<void> {
        await this.getTopicTree().locator(`text=${topicText}`).click();
        await this.waitForCanvasStable();
    }

    // ==================== Colormap ====================

    /**
     * Get the colormap selector element.
     */
    getColormapSelector(): Locator {
        return this.page.locator('#colormap-selector');
    }

    /**
     * Check if colormap selection is enabled.
     */
    async hasColormapSelector(): Promise<boolean> {
        return await this.getColormapSelector().isVisible().catch(() => false);
    }

    /**
     * Select a colormap by name or index.
     */
    async selectColormap(value: string): Promise<void> {
        await this.getColormapSelector().selectOption(value);
        await this.waitForCanvasStable();
    }

    // ==================== Click Actions ====================

    /**
     * Click on the canvas at a specific position.
     */
    async clickAt(x: number, y: number): Promise<void> {
        await this.page.mouse.click(x, y);
    }

    // ==================== Screenshot Helpers ====================

    /**
     * Take a screenshot of the canvas and compare to baseline.
     */
    async expectCanvasScreenshot(name: string, options?: { timeout?: number }): Promise<void> {
        const canvas = await this.waitForCanvasStable();
        await expect(canvas).toHaveScreenshot(name, {
            timeout: options?.timeout ?? 180_000,
        });
    }

    // ==================== Utility Methods ====================

    /**
     * Get the canvas dimensions.
     */
    async getCanvasSize(): Promise<{ width: number; height: number }> {
        return await this.page.evaluate(() => {
            const canvas = document.querySelector('#deck-container canvas');
            return {
                width: (canvas as HTMLCanvasElement)?.width ?? 0,
                height: (canvas as HTMLCanvasElement)?.height ?? 0,
            };
        });
    }

    /**
     * Check if the page is in dark mode.
     */
    async isDarkMode(): Promise<boolean> {
        return await this.page.evaluate(() => {
            const body = document.body;
            const bgColor = window.getComputedStyle(body).backgroundColor;
            // Simple heuristic: if background is dark, we're in dark mode
            const rgb = bgColor.match(/\d+/g);
            if (rgb && rgb.length >= 3) {
                const brightness = (parseInt(rgb[0]) + parseInt(rgb[1]) + parseInt(rgb[2])) / 3;
                return brightness < 128;
            }
            return false;
        });
    }

    /**
     * Check if we're running on a mobile device.
     */
    isMobile(testInfo: any): boolean {
        return testInfo?.project?.name?.includes('mobile') ?? false;
    }
}
