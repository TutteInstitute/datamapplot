/**
 * MiniMap - Overview map showing entire dataset with viewport indicator
 */
class MiniMap {
    constructor(container, datamap, options = {}) {
        this.container = container;
        this.datamap = datamap;

        this.options = {
            width: options.width || 200,
            height: options.height || 150,
            updateThrottle: options.updateThrottle || 200,
            borderColor: options.borderColor || '#3ba5e7',
            borderWidth: options.borderWidth || 2,
            backgroundColor: options.backgroundColor || '#f5f5f5',
            pointColor: options.pointColor || '#666666',
            pointSize: options.pointSize || 2,
            mirrorY: options.mirrorY || false,
        };

        this.canvas = null;
        this.ctx = null;
        this.viewportOverlay = null;
        this.bounds = null;
        this.scale = 1;
        this.offset = { x: 0, y: 0 };

        this.throttledUpdate = this.throttle(this.updateViewport.bind(this), this.options.updateThrottle);

        this.render();
        this.attachEventListeners();
        this.initialize();
    }

    render() {
        this.container.innerHTML = '';
        this.container.style.width = `${this.options.width}px`;
        this.container.style.height = `${this.options.height}px`;
        this.container.style.position = 'relative';
        this.container.style.background = this.options.backgroundColor;
        this.container.style.borderRadius = '4px';
        this.container.style.overflow = 'hidden';

        // Create canvas for rendering points
        this.canvas = document.createElement('canvas');
        this.canvas.width = this.options.width;
        this.canvas.height = this.options.height;
        this.canvas.style.position = 'absolute';
        this.canvas.style.top = '0';
        this.canvas.style.left = '0';
        this.canvas.className = 'minimap-canvas';
        this.container.appendChild(this.canvas);

        this.ctx = this.canvas.getContext('2d');

        // Create viewport indicator overlay
        this.viewportOverlay = document.createElement('div');
        this.viewportOverlay.className = 'minimap-viewport-indicator';
        this.viewportOverlay.style.position = 'absolute';
        this.viewportOverlay.style.border = `${this.options.borderWidth}px solid ${this.options.borderColor}`;
        this.viewportOverlay.style.pointerEvents = 'auto';
        this.viewportOverlay.style.boxSizing = 'border-box';
        this.viewportOverlay.style.cursor = 'move';
        this.container.appendChild(this.viewportOverlay);
    }

    async initialize() {
        // Wait for datamap to be ready
        if (!this.datamap.pointData) {
            await new Promise(resolve => {
                const checkInterval = setInterval(() => {
                    if (this.datamap.pointData) {
                        clearInterval(checkInterval);
                        resolve();
                    }
                }, 100);
            });
        }

        this.calculateBounds();
        this.renderPoints();
        this.updateViewport();
        this.currentViewState = this.datamap.deckgl ? (this.datamap.deckgl.viewState || this.datamap.deckgl.props.initialViewState) : null;
    }

    calculateBounds() {
        const data = this.datamap.pointData;
        if (!data || !data.x || !data.y) return;

        let minX = Infinity, maxX = -Infinity;
        let minY = Infinity, maxY = -Infinity;

        for (let i = 0; i < data.x.length; i++) {
            minX = Math.min(minX, data.x[i]);
            maxX = Math.max(maxX, data.x[i]);
            minY = Math.min(minY, data.y[i]);
            maxY = Math.max(maxY, data.y[i]);
        }

        this.bounds = { minX, maxX, minY, maxY };

        // Calculate scale and offset to fit points in canvas
        const dataWidth = maxX - minX;
        const dataHeight = maxY - minY;
        const padding = 10;

        const scaleX = (this.options.width - 2 * padding) / dataWidth;
        const scaleY = (this.options.height - 2 * padding) / dataHeight;
        this.scale = Math.min(scaleX, scaleY);

        this.offset = {
            x: padding + (this.options.width - 2 * padding - dataWidth * this.scale) / 2,
            y: padding + (this.options.height - 2 * padding - dataHeight * this.scale) / 2
        };
    }

    renderPoints() {
        if (!this.ctx || !this.bounds) return;

        const data = this.datamap.pointData;
        if (!data) return;

        // Clear canvas
        this.ctx.clearRect(0, 0, this.options.width, this.options.height);

        // Draw points
        this.ctx.fillStyle = this.options.pointColor;

        for (let i = 0; i < data.x.length; i++) {
            const x = this.projectX(data.x[i]);
            const y = this.projectY(data.y[i]);

            this.ctx.fillRect(
                x - this.options.pointSize / 2,
                y - this.options.pointSize / 2,
                this.options.pointSize,
                this.options.pointSize
            );
        }
    }

    projectX(x) {
        return (x - this.bounds.minX) * this.scale + this.offset.x;
    }

    projectY(y) {
        if (this.options.mirrorY) {
            return (y - this.bounds.minY) * this.scale + this.offset.y;
        } else {
            return (this.bounds.maxY - y) * this.scale + this.offset.y;
        }
    }

    updateViewport() {
        if (!this.datamap.deckgl || !this.bounds) return;

        const viewState = this.datamap.deckgl.viewState || this.datamap.deckgl.props.initialViewState;
        if (!viewState) return;

        // Get viewport bounds from deck.gl
        const viewport = this.datamap.deckgl.getViewports()[0];
        if (!viewport) return;

        // Calculate viewport corners in data coordinates
        const topLeft = viewport.unproject([0, 0]);
        const bottomRight = viewport.unproject([viewport.width, viewport.height]);

        // Project to minimap coordinates
        const left = this.projectX(topLeft[0]);
        const right = this.projectX(bottomRight[0]);
        const top = this.projectY(topLeft[1]);
        const bottom = this.projectY(bottomRight[1]);

        // Update viewport indicator
        const width = Math.abs(right - left);
        const height = Math.abs(bottom - top);

        this.viewportOverlay.style.left = `${Math.min(left, right)}px`;
        this.viewportOverlay.style.top = `${Math.min(top, bottom)}px`;
        this.viewportOverlay.style.width = `${width}px`;
        this.viewportOverlay.style.height = `${height}px`;
    }

    attachEventListeners() {
        // Listen to deck.gl view state changes
        if (this.datamap.deckgl) {
            // Guard flag: when true we are inside a synthetic notification
            // triggered by _notifyViewStateChange.  The minimap's own handler
            // should still forward to the chain but must NOT update viewState
            // or setProps (we already did that before the notification).
            this._isNotifying = false;

            this._chainedOnViewStateChange =
                this.datamap.deckgl.props.onViewStateChange || null;

            this.datamap.deckgl.setProps({
                onViewStateChange: (params) => {
                    // Always forward to the rest of the chain so every
                    // handler (annotation widget, topic-tree, etc.) runs.
                    if (this._chainedOnViewStateChange) {
                        this._chainedOnViewStateChange(params);
                    }
                    // Skip minimap-specific logic when this call originates
                    // from our own programmatic view-state update.
                    if (!this._isNotifying) {
                        this.throttledUpdate();
                        this.currentViewState = params.viewState;
                        this.datamap.deckgl.setProps({
                            initialViewState: this.currentViewState
                        });
                    }
                    return params.viewState;
                }
            });
        }

        // Click to navigate
        this.canvas.addEventListener('click', (e) => {
            this.handleClick(e);
        });

        this.canvas.style.cursor = 'pointer';

        // Drag viewport indicator
        let isDragging = false;
        let dragStartX = 0;
        let dragStartY = 0;
        let viewportStartX = 0;
        let viewportStartY = 0;

        this.viewportOverlay.addEventListener('mousedown', (e) => {
            isDragging = true;
            dragStartX = e.clientX;
            dragStartY = e.clientY;

            // Read position from style (canvas-local coordinates) rather than
            // getBoundingClientRect (screen coordinates) so we stay in the same
            // coordinate system as the canvas and the unprojection math, even
            // when the parent stack has CSS transform: scaleY(-1).
            viewportStartX = parseFloat(this.viewportOverlay.style.left) || 0;
            viewportStartY = parseFloat(this.viewportOverlay.style.top) || 0;

            e.preventDefault();
            e.stopPropagation();
        });

        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;

            const dx = e.clientX - dragStartX;
            // When mirrorY is true the minimap sits inside a CSS scaleY(-1)
            // parent, so screen-space down corresponds to local-space up.
            // Negate the delta so dragging moves the viewport in the visually
            // correct direction.
            const dy = this.options.mirrorY
                ? -(e.clientY - dragStartY)
                : (e.clientY - dragStartY);

            const newX = viewportStartX + dx;
            const newY = viewportStartY + dy;

            // Unproject center of viewport box to data coordinates
            const viewportWidth = parseFloat(this.viewportOverlay.style.width);
            const viewportHeight = parseFloat(this.viewportOverlay.style.height);
            const centerX = newX + viewportWidth / 2;
            const centerY = newY + viewportHeight / 2;

            const dataX = (centerX - this.offset.x) / this.scale + this.bounds.minX;
            const dataY = this.options.mirrorY
                ? (centerY - this.offset.y) / this.scale + this.bounds.minY
                : this.bounds.maxY - (centerY - this.offset.y) / this.scale;
            const dataZoom = this.currentViewState.zoom;

            // Update deck.gl via initialViewState
            // When controller is enabled, changing initialViewState updates the view
            const currentViewState = this.datamap.deckgl.props.initialViewState;
            const newViewState = {
                ...currentViewState,
                longitude: dataX,
                latitude: dataY,
                zoom: dataZoom,
                transitionDuration: 0
            };
            this.datamap.deckgl.setProps({
                initialViewState: newViewState
            });
            // Notify chained handlers (annotation widget etc.) that the
            // view changed — deck.gl does not fire onViewStateChange for
            // programmatic initialViewState updates.
            this._notifyViewStateChange(newViewState);
            this.throttledUpdate();

            e.preventDefault();
        });

        document.addEventListener('mouseup', () => {
            isDragging = false;
        });
    }

    handleClick(e) {
        if (!this.bounds || !this.datamap.deckgl) return;

        const rect = this.canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        // When mirrorY is true the minimap is inside a CSS scaleY(-1) parent,
        // so screen-space y is inverted relative to canvas-local y.
        let y = e.clientY - rect.top;
        if (this.options.mirrorY) {
            y = this.options.height - y;
        }

        // Unproject from minimap to data coordinates
        const dataX = (x - this.offset.x) / this.scale + this.bounds.minX;
        const dataY = this.options.mirrorY
            ? (y - this.offset.y) / this.scale + this.bounds.minY
            : this.bounds.maxY - (y - this.offset.y) / this.scale;

        // Get current view state
        const currentViewState = this.datamap.deckgl.viewState || this.datamap.deckgl.props.initialViewState;

        // Set new view state centered on clicked point with transition
        const newViewState = {
            ...currentViewState,
            longitude: dataX,
            latitude: dataY,
            transitionDuration: 500,
            transitionInterpolator: new deck.LinearInterpolator(['longitude', 'latitude'])
        };

        this.datamap.deckgl.setProps({
            initialViewState: newViewState
        });
        // Notify chained handlers (annotation widget etc.)
        this._notifyViewStateChange(newViewState);
    }

    /**
     * Explicitly invoke the full onViewStateChange handler chain after a
     * programmatic view-state update.  deck.gl only fires the callback
     * for user-initiated interactions, so we synthesize the call here
     * to keep layers like the annotation overlay in sync.
     *
     * We call the CURRENT top-of-chain handler from deckgl.props rather
     * than the one captured at init time, because other widgets (e.g.
     * AnnotationWidget) may install their handlers after the minimap.
     * A reentrancy guard (_isNotifying) prevents the minimap's own
     * handler from re-triggering setProps / throttledUpdate.
     */
    _notifyViewStateChange(viewState) {
        const handler = this.datamap.deckgl.props.onViewStateChange;
        if (!handler) return;
        this._isNotifying = true;
        try {
            handler({ viewState });
        } finally {
            this._isNotifying = false;
        }
    }

    throttle(func, wait) {
        let timeout = null;
        let previous = 0;

        return function (...args) {
            const now = Date.now();
            const remaining = wait - (now - previous);

            if (remaining <= 0) {
                if (timeout) {
                    clearTimeout(timeout);
                    timeout = null;
                }
                previous = now;
                func.apply(this, args);
            } else if (!timeout) {
                timeout = setTimeout(() => {
                    previous = Date.now();
                    timeout = null;
                    func.apply(this, args);
                }, remaining);
            }
        };
    }

    // Public method to refresh the minimap
    refresh() {
        this.calculateBounds();
        this.renderPoints();
        this.updateViewport();
    }
}
