/**
 * AnnotationWidget — Canvas-based annotation overlay for DataMapPlot
 *
 * All annotations live on a single HTML5 Canvas that sits over the deck.gl
 * viewport.  Coordinates are stored in data-space (the same x/y used by
 * the scatter plot) and re-projected to screen pixels on every viewstate
 * change, so annotations track with pan / zoom automatically.
 *
 * No deck.gl layers are created — this completely avoids layer-management
 * conflicts with the DataMap core.
 *
 * Coordinate system:
 *   data  coords  — the original x,y from the dataset
 *   screen coords  — CSS pixels from top-left of the viewport
 */

// ===== Annotation Data Models =====

class Annotation {
    constructor(id, type) {
        this.id = id || `ann-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        this.type = type;
        this.created = Date.now();
        this.modified = Date.now();
    }
    toJSON() {
        return { id: this.id, type: this.type, created: this.created, modified: this.modified };
    }
}

class TextAnnotation extends Annotation {
    constructor(id, position, text, options = {}) {
        super(id, 'text');
        this.position = position;                          // {x, y} data coords
        this.text = text;
        this.color = options.color || '#000000';
        this.size = options.size || 14;                    // base font size (px)
        this.fontWeight = options.fontWeight || 'normal';
        this.fontFamily = options.fontFamily || 'Arial, sans-serif';
        this.backgroundColor = options.backgroundColor || null;
        this.padding = options.padding || 4;
        this.createdAtZoom = options.createdAtZoom || null; // zoom level when created
    }
    toJSON() {
        return {
            ...super.toJSON(), position: this.position, text: this.text,
            color: this.color, size: this.size, fontWeight: this.fontWeight,
            fontFamily: this.fontFamily, backgroundColor: this.backgroundColor,
            padding: this.padding, createdAtZoom: this.createdAtZoom,
        };
    }
}

class ArrowAnnotation extends Annotation {
    constructor(id, start, end, options = {}) {
        super(id, 'arrow');
        this.start = start;  // {x, y}
        this.end = end;
        this.color = options.color || '#FF0000';
        this.width = options.width || 2;
        this.arrowheadSize = options.arrowheadSize || 10;
    }
    toJSON() {
        return {
            ...super.toJSON(), start: this.start, end: this.end,
            color: this.color, width: this.width, arrowheadSize: this.arrowheadSize,
        };
    }
}

class CircleAnnotation extends Annotation {
    constructor(id, center, radius, options = {}) {
        super(id, 'circle');
        this.center = center;
        this.radius = radius;   // data-space units
        this.strokeColor = options.strokeColor || '#FF0000';
        this.strokeWidth = options.strokeWidth || 2;
        this.fillColor = options.fillColor || '#FF0000';
        this.fillOpacity = options.fillOpacity || 0.2;
    }
    toJSON() {
        return {
            ...super.toJSON(), center: this.center, radius: this.radius,
            strokeColor: this.strokeColor, strokeWidth: this.strokeWidth,
            fillColor: this.fillColor, fillOpacity: this.fillOpacity,
        };
    }
}

class RectangleAnnotation extends Annotation {
    constructor(id, topLeft, bottomRight, options = {}) {
        super(id, 'rectangle');
        this.topLeft = topLeft;
        this.bottomRight = bottomRight;
        this.strokeColor = options.strokeColor || '#FF0000';
        this.strokeWidth = options.strokeWidth || 2;
        this.fillColor = options.fillColor || '#FF0000';
        this.fillOpacity = options.fillOpacity || 0.2;
    }
    toJSON() {
        return {
            ...super.toJSON(), topLeft: this.topLeft, bottomRight: this.bottomRight,
            strokeColor: this.strokeColor, strokeWidth: this.strokeWidth,
            fillColor: this.fillColor, fillOpacity: this.fillOpacity,
        };
    }
}

// ===== Main Widget Class =====

class AnnotationWidget {
    constructor(containerId, config, datamap) {
        this.containerId = containerId;
        this.config = config;
        this.datamap = datamap;

        // State
        this.annotations = [];
        this.currentTool = null;       // 'text' | 'arrow' | 'circle' | 'rectangle' | null
        this.drawingState = null;      // in-progress shape while dragging
        this.selectedAnnotation = null;

        // Canvas references (created in initCanvas)
        this.canvas = null;
        this.ctx = null;

        // Inline text input reference
        this._textInput = null;

        // For chaining deck.gl callbacks
        this._origOnViewStateChange = null;

        // Resize observer
        this._resizeObserver = null;

        // Pending redraw frame id
        this._rafId = null;

        this.initialize();
    }

    // ------------------------------------------------------------------
    //  Initialisation
    // ------------------------------------------------------------------

    initialize() {
        const container = document.getElementById(this.containerId);
        if (!container) {
            console.error(`AnnotationWidget: container #${this.containerId} not found`);
            return;
        }

        this.renderToolbar(container);
        this.initCanvas();
        this.attachToolbarListeners();
        this.attachDrawingListeners();
        this.hookViewStateChange();

        if (this.config.initial_annotations && this.config.initial_annotations.length > 0) {
            this.loadAnnotations(this.config.initial_annotations);
        }
    }

    // ------------------------------------------------------------------
    //  Canvas setup
    // ------------------------------------------------------------------

    initCanvas() {
        this.canvas = document.createElement('canvas');
        this.canvas.className = 'annotation-overlay-canvas';
        this.canvas.style.position = 'fixed';
        this.canvas.style.top = '0';
        this.canvas.style.left = '0';
        this.canvas.style.zIndex = '50';
        this.canvas.style.pointerEvents = 'none';     // pass-through by default
        document.body.appendChild(this.canvas);

        this.ctx = this.canvas.getContext('2d');
        this._sizeCanvas();

        // Re-size whenever the viewport changes
        this._resizeObserver = new ResizeObserver(() => {
            this._sizeCanvas();
            this.redraw();
        });
        this._resizeObserver.observe(this.datamap.container);
    }

    _sizeCanvas() {
        const dpr = window.devicePixelRatio || 1;
        const w = this.datamap.container.clientWidth;
        const h = this.datamap.container.clientHeight;
        this.canvas.style.width = w + 'px';
        this.canvas.style.height = h + 'px';
        this.canvas.width = w * dpr;
        this.canvas.height = h * dpr;
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);   // scale once
    }

    // ------------------------------------------------------------------
    //  View-state hook  (re-render on every pan / zoom)
    // ------------------------------------------------------------------

    hookViewStateChange() {
        this._origOnViewStateChange = this.datamap.deckgl.props.onViewStateChange || null;

        this.datamap.deckgl.setProps({
            onViewStateChange: (params) => {
                // Call any previously-chained handler first
                if (this._origOnViewStateChange) {
                    this._origOnViewStateChange(params);
                }
                this.scheduleRedraw();
                return params.viewState;
            },
        });
    }

    scheduleRedraw() {
        if (this._rafId) return;                       // already scheduled
        this._rafId = requestAnimationFrame(() => {
            this._rafId = null;
            this.redraw();
        });
    }

    // ------------------------------------------------------------------
    //  Coordinate helpers  (use deck.gl's own viewport, like the lasso)
    // ------------------------------------------------------------------

    _getViewport() {
        return (
            this.datamap.deckgl.viewManager?.getViewports()[0] ||
            this.datamap.deckgl.getViewports?.()[0] ||
            null
        );
    }

    _getCurrentZoom() {
        const vs = this.datamap.deckgl.viewState || this.datamap.deckgl.props.initialViewState;
        return vs ? vs.zoom : 0;
    }

    screenToData(sx, sy) {
        const vp = this._getViewport();
        if (!vp) return { x: 0, y: 0 };
        const [x, y] = vp.unproject([sx, sy]);
        return { x, y };
    }

    dataToScreen(x, y) {
        const vp = this._getViewport();
        if (!vp) return [0, 0];
        return vp.project([x, y]);                     // [screenX, screenY]
    }

    // ------------------------------------------------------------------
    //  Toolbar rendering  (lives inside the drawer container)
    // ------------------------------------------------------------------

    renderToolbar(container) {
        const t = this.config.tools;
        container.innerHTML = `
        <div class="annotation-widget">
            <div class="annotation-toolbar">
                <div class="annotation-tool-group">
                    ${t.text ? `<button class="annotation-tool-btn" data-tool="text" title="Add text"><svg width="20" height="20" viewBox="0 0 24 24"><path d="M5 4v3h5.5v12h3V7H19V4z"/></svg></button>` : ''}
                    ${t.arrow ? `<button class="annotation-tool-btn" data-tool="arrow" title="Draw arrow"><svg width="20" height="20" viewBox="0 0 24 24"><path d="M16.01 11H4v2h12.01v3L20 12l-3.99-4z"/></svg></button>` : ''}
                    ${t.circle ? `<button class="annotation-tool-btn" data-tool="circle" title="Draw circle"><svg width="20" height="20" viewBox="0 0 24 24"><circle cx="12" cy="12" r="8" fill="none" stroke="currentColor" stroke-width="2"/></svg></button>` : ''}
                    ${t.rectangle ? `<button class="annotation-tool-btn" data-tool="rectangle" title="Draw rectangle"><svg width="20" height="20" viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"/></svg></button>` : ''}
                </div>
                <div class="annotation-tool-group">
                    <button class="annotation-action-btn" data-action="delete" title="Delete selected" disabled>
                        <svg width="20" height="20" viewBox="0 0 24 24"><path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg>
                    </button>
                    <button class="annotation-action-btn" data-action="clear" title="Clear all">
                        <svg width="20" height="20" viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
                    </button>
                </div>
                ${this.config.features.export || this.config.features.import ? `
                <div class="annotation-tool-group">
                    ${this.config.features.export ? `<button class="annotation-action-btn" data-action="export" title="Export annotations"><svg width="20" height="20" viewBox="0 0 24 24"><path d="M19 12v7H5v-7H3v7c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2v-7h-2zm-6 .67l2.59-2.58L17 11.5l-5 5-5-5 1.41-1.41L11 12.67V3h2z"/></svg></button>` : ''}
                    ${this.config.features.import ? `
                        <button class="annotation-action-btn" data-action="import" title="Import annotations"><svg width="20" height="20" viewBox="0 0 24 24"><path d="M19 12v7H5v-7H3v7c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2v-7h-2zm-6-.67l2.59 2.58L17 12.5l-5-5-5 5 1.41 1.41L11 11.33V21h2z"/></svg></button>
                        <input type="file" id="${this.containerId}-import-file" accept=".json" style="display:none;" />
                    ` : ''}
                </div>` : ''}
            </div>
            <div class="annotation-list">
                <div class="annotation-list-header">Annotations (<span class="annotation-count">0</span>)</div>
                <div class="annotation-list-items"></div>
            </div>
        </div>`;
    }

    // ------------------------------------------------------------------
    //  Toolbar event wiring
    // ------------------------------------------------------------------

    attachToolbarListeners() {
        const root = document.getElementById(this.containerId);

        // Tool buttons
        root.querySelectorAll('.annotation-tool-btn').forEach(btn => {
            btn.addEventListener('click', () => this.selectTool(btn.dataset.tool));
        });

        // Action buttons
        root.querySelectorAll('.annotation-action-btn').forEach(btn => {
            btn.addEventListener('click', () => this.handleAction(btn.dataset.action));
        });

        // Import file input
        if (this.config.features.import) {
            const fileInput = document.getElementById(`${this.containerId}-import-file`);
            if (fileInput) fileInput.addEventListener('change', (e) => this.handleImport(e));
        }
    }

    // ------------------------------------------------------------------
    //  Tool selection  (enable / disable drawing mode)
    // ------------------------------------------------------------------

    selectTool(tool) {
        // Toggle off if same tool clicked again
        this.currentTool = this.currentTool === tool ? null : tool;

        // Button highlight
        document.querySelectorAll(`#${this.containerId} .annotation-tool-btn`).forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tool === this.currentTool);
        });

        this._setDrawingMode(!!this.currentTool);
    }

    /** Enable / disable drawing mode (pointer capture + deck.gl controller). */
    _setDrawingMode(active) {
        // Canvas pointer-events
        this.canvas.style.pointerEvents = active ? 'all' : 'none';

        // Deck.gl controller
        this.datamap.deckgl.setProps({
            controller: {
                scrollZoom: { speed: 0.01, smooth: true },
                dragPan: !active,
                dragRotate: !active,
            },
            getCursor: active
                ? () => 'crosshair'
                : ({ isDragging }) => isDragging ? 'grabbing' : 'grab',
        });
    }

    // ------------------------------------------------------------------
    //  Drawing interaction  (mouse events on the overlay canvas)
    // ------------------------------------------------------------------

    attachDrawingListeners() {
        // We listen on window so that drags that leave the canvas still complete.
        // Each handler is a bound reference so we can remove them in destroy().
        this._onMouseDown = this._handleMouseDown.bind(this);
        this._onMouseMove = this._handleMouseMove.bind(this);
        this._onMouseUp = this._handleMouseUp.bind(this);
        this._onKeyDown = this._handleKeyDown.bind(this);

        window.addEventListener('mousedown', this._onMouseDown);
        window.addEventListener('mousemove', this._onMouseMove);
        window.addEventListener('mouseup', this._onMouseUp);
        window.addEventListener('keydown', this._onKeyDown);
    }

    _handleKeyDown(e) {
        if (e.key === 'Escape') {
            // Cancel in-progress drawing or deselect tool
            if (this.drawingState) {
                this.drawingState = null;
                this.redraw();
            }
            if (this._textInput) this._removeTextInput();
            if (this.currentTool) this.selectTool(null);
        }
    }

    _handleMouseDown(e) {
        if (!this.currentTool) return;
        // Only respond to clicks on our overlay canvas
        if (e.target !== this.canvas) return;

        const coords = this.screenToData(e.clientX, e.clientY);

        if (this.currentTool === 'text') {
            this._showTextInput(e.clientX, e.clientY, coords);
            return;
        }

        // Start a drag for arrow / circle / rectangle
        this.drawingState = {
            tool: this.currentTool,
            startData: coords,
            currentData: coords,
        };
    }

    _handleMouseMove(e) {
        if (!this.drawingState) return;
        this.drawingState.currentData = this.screenToData(e.clientX, e.clientY);
        this.redraw();   // includes the live preview
    }

    _handleMouseUp(e) {
        if (!this.drawingState) return;
        const { tool, startData } = this.drawingState;
        const endData = this.screenToData(e.clientX, e.clientY);
        this.drawingState = null;

        // Ignore tiny drags (accidental clicks)
        const [sx, sy] = this.dataToScreen(startData.x, startData.y);
        const [ex, ey] = this.dataToScreen(endData.x, endData.y);
        if (Math.hypot(ex - sx, ey - sy) < 4) { this.redraw(); return; }

        if (tool === 'arrow') {
            this._commitArrow(startData, endData);
        } else if (tool === 'circle') {
            const r = Math.hypot(endData.x - startData.x, endData.y - startData.y);
            this._commitCircle(startData, r);
        } else if (tool === 'rectangle') {
            this._commitRectangle(startData, endData);
        }

        this.selectTool(null);   // deselect after drawing
    }

    // ------------------------------------------------------------------
    //  Inline text input
    // ------------------------------------------------------------------

    _showTextInput(screenX, screenY, dataCoords) {
        // Remove any existing input first
        if (this._textInput) this._removeTextInput();

        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'annotation-text-input';
        input.style.position = 'fixed';
        input.style.left = screenX + 'px';
        input.style.top = screenY + 'px';
        input.style.zIndex = '60';
        input.style.fontSize = this.config.defaults.text_size + 'px';
        input.style.color = this.config.defaults.text_color;
        input.placeholder = 'Type annotation…';
        document.body.appendChild(input);
        input.focus();

        this._textInput = input;
        this._textInputDataCoords = dataCoords;

        const commit = () => {
            const text = input.value.trim();
            if (text) {
                this._commitText(this._textInputDataCoords, text);
            }
            this._removeTextInput();
            this.selectTool(null);
        };

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') { e.preventDefault(); commit(); }
            if (e.key === 'Escape') { this._removeTextInput(); this.selectTool(null); }
        });
        input.addEventListener('blur', commit);
    }

    _removeTextInput() {
        if (this._textInput && this._textInput.parentNode) {
            this._textInput.parentNode.removeChild(this._textInput);
        }
        this._textInput = null;
        this._textInputDataCoords = null;
    }

    // ------------------------------------------------------------------
    //  Annotation creation helpers
    // ------------------------------------------------------------------

    _commitText(position, text) {
        this.addAnnotation(new TextAnnotation(null, position, text, {
            color: this.config.defaults.text_color,
            size: this.config.defaults.text_size,
            createdAtZoom: this._getCurrentZoom(),
        }));
    }

    _commitArrow(start, end) {
        this.addAnnotation(new ArrowAnnotation(null, start, end, {
            color: this.config.defaults.stroke_color,
            width: this.config.defaults.stroke_width,
        }));
    }

    _commitCircle(center, radius) {
        this.addAnnotation(new CircleAnnotation(null, center, radius, {
            strokeColor: this.config.defaults.stroke_color,
            strokeWidth: this.config.defaults.stroke_width,
            fillColor: this.config.defaults.stroke_color,
            fillOpacity: this.config.defaults.fill_opacity,
        }));
    }

    _commitRectangle(topLeft, bottomRight) {
        this.addAnnotation(new RectangleAnnotation(null, topLeft, bottomRight, {
            strokeColor: this.config.defaults.stroke_color,
            strokeWidth: this.config.defaults.stroke_width,
            fillColor: this.config.defaults.stroke_color,
            fillOpacity: this.config.defaults.fill_opacity,
        }));
    }

    // ------------------------------------------------------------------
    //  Annotation storage
    // ------------------------------------------------------------------

    addAnnotation(annotation) {
        this.annotations.push(annotation);
        this.updateAnnotationList();
        this.redraw();
    }

    deleteAnnotation(annotationId) {
        if (this.selectedAnnotation && this.selectedAnnotation.id === annotationId) {
            this.selectedAnnotation = null;
            this._updateDeleteButton();
        }
        this.annotations = this.annotations.filter(a => a.id !== annotationId);
        this.updateAnnotationList();
        this.redraw();
    }

    clearAnnotations() {
        if (this.annotations.length === 0) return;
        if (!confirm(`Delete all ${this.annotations.length} annotations?`)) return;
        this.annotations = [];
        this.selectedAnnotation = null;
        this._updateDeleteButton();
        this.updateAnnotationList();
        this.redraw();
    }

    selectAnnotation(annotationId) {
        this.selectedAnnotation = this.annotations.find(a => a.id === annotationId) || null;
        this._updateDeleteButton();
        this._highlightListItem();
        this.redraw();
    }

    _updateDeleteButton() {
        const btn = document.querySelector(`#${this.containerId} [data-action="delete"]`);
        if (btn) btn.disabled = !this.selectedAnnotation;
    }

    // ------------------------------------------------------------------
    //  Annotation list  (sidebar UI)
    // ------------------------------------------------------------------

    updateAnnotationList() {
        const list = document.querySelector(`#${this.containerId} .annotation-list-items`);
        const count = document.querySelector(`#${this.containerId} .annotation-count`);
        if (!list || !count) return;

        count.textContent = this.annotations.length;
        list.innerHTML = this.annotations.map(a => {
            const label = a.type === 'text'
                ? `Text: "${a.text.length > 20 ? a.text.substring(0, 20) + '…' : a.text}"`
                : a.type.charAt(0).toUpperCase() + a.type.slice(1);
            return `<div class="annotation-list-item" data-id="${a.id}">
                <span class="annotation-list-label">${label}</span>
                <button class="annotation-list-delete" data-id="${a.id}" title="Delete">×</button>
            </div>`;
        }).join('');

        // Wire up per-item listeners
        list.querySelectorAll('.annotation-list-item').forEach(item => {
            item.addEventListener('click', () => this.selectAnnotation(item.dataset.id));
        });
        list.querySelectorAll('.annotation-list-delete').forEach(btn => {
            btn.addEventListener('click', (e) => { e.stopPropagation(); this.deleteAnnotation(btn.dataset.id); });
        });
        this._highlightListItem();
    }

    _highlightListItem() {
        document.querySelectorAll(`#${this.containerId} .annotation-list-item`).forEach(item => {
            item.classList.toggle('selected', item.dataset.id === (this.selectedAnnotation?.id));
        });
    }

    // ------------------------------------------------------------------
    //  Canvas redraw  (the heart of the overlay approach)
    // ------------------------------------------------------------------

    redraw() {
        const ctx = this.ctx;
        const w = this.canvas.width / (window.devicePixelRatio || 1);
        const h = this.canvas.height / (window.devicePixelRatio || 1);
        ctx.clearRect(0, 0, w, h);

        // Draw committed annotations
        for (const a of this.annotations) {
            const isSelected = this.selectedAnnotation && this.selectedAnnotation.id === a.id;
            this._drawAnnotation(ctx, a, isSelected);
        }

        // Draw in-progress preview
        if (this.drawingState) {
            this._drawPreview(ctx, this.drawingState);
        }
    }

    _drawAnnotation(ctx, a, highlight) {
        if (a.type === 'text')      this._drawText(ctx, a, highlight);
        if (a.type === 'arrow')     this._drawArrow(ctx, a, highlight);
        if (a.type === 'circle')    this._drawCircle(ctx, a, highlight);
        if (a.type === 'rectangle') this._drawRectangle(ctx, a, highlight);
    }

    // ---- Text ----
    _drawText(ctx, a, highlight) {
        const [sx, sy] = this.dataToScreen(a.position.x, a.position.y);

        // Scale font size relative to the zoom when the text was created
        let fontSize = a.size;
        if (a.createdAtZoom != null) {
            const zoomDelta = this._getCurrentZoom() - a.createdAtZoom;
            fontSize = a.size * Math.pow(2, zoomDelta);
            fontSize = Math.max(4, Math.min(fontSize, 200));   // clamp
        }

        ctx.save();
        ctx.font = `${a.fontWeight} ${fontSize}px ${a.fontFamily}`;
        ctx.textAlign = 'left';
        ctx.textBaseline = 'top';

        // Background
        if (a.backgroundColor || highlight) {
            const metrics = ctx.measureText(a.text);
            const pad = a.padding;
            const bx = sx - pad;
            const by = sy - pad;
            const bw = metrics.width + pad * 2;
            const bh = fontSize + pad * 2;
            ctx.fillStyle = highlight ? 'rgba(25,118,210,0.15)' : a.backgroundColor;
            ctx.fillRect(bx, by, bw, bh);
            if (highlight) {
                ctx.strokeStyle = '#1976d2';
                ctx.lineWidth = 1.5;
                ctx.strokeRect(bx, by, bw, bh);
            }
        }

        ctx.fillStyle = a.color;
        ctx.fillText(a.text, sx, sy);
        ctx.restore();
    }

    // ---- Arrow ----
    _drawArrow(ctx, a, highlight) {
        const [sx, sy] = this.dataToScreen(a.start.x, a.start.y);
        const [ex, ey] = this.dataToScreen(a.end.x, a.end.y);

        ctx.save();
        ctx.strokeStyle = a.color;
        ctx.lineWidth = highlight ? a.width + 2 : a.width;
        ctx.lineCap = 'round';

        if (highlight) {
            ctx.shadowColor = '#1976d2';
            ctx.shadowBlur = 6;
        }

        // Shaft
        ctx.beginPath();
        ctx.moveTo(sx, sy);
        ctx.lineTo(ex, ey);
        ctx.stroke();

        // Arrowhead
        const angle = Math.atan2(ey - sy, ex - sx);
        const headLen = a.arrowheadSize;
        ctx.fillStyle = a.color;
        ctx.beginPath();
        ctx.moveTo(ex, ey);
        ctx.lineTo(ex - headLen * Math.cos(angle - Math.PI / 6), ey - headLen * Math.sin(angle - Math.PI / 6));
        ctx.lineTo(ex - headLen * Math.cos(angle + Math.PI / 6), ey - headLen * Math.sin(angle + Math.PI / 6));
        ctx.closePath();
        ctx.fill();
        ctx.restore();
    }

    // ---- Circle ----
    _drawCircle(ctx, a, highlight) {
        const [cx, cy] = this.dataToScreen(a.center.x, a.center.y);
        // Convert data-space radius to screen pixels
        const [ex, ey] = this.dataToScreen(a.center.x + a.radius, a.center.y);
        const screenRadius = Math.hypot(ex - cx, ey - cy);

        ctx.save();
        if (highlight) { ctx.shadowColor = '#1976d2'; ctx.shadowBlur = 6; }

        // Fill
        ctx.beginPath();
        ctx.arc(cx, cy, screenRadius, 0, Math.PI * 2);
        ctx.fillStyle = this._withAlpha(a.fillColor, a.fillOpacity);
        ctx.fill();

        // Stroke
        ctx.strokeStyle = a.strokeColor;
        ctx.lineWidth = highlight ? a.strokeWidth + 2 : a.strokeWidth;
        ctx.stroke();
        ctx.restore();
    }

    // ---- Rectangle ----
    _drawRectangle(ctx, a, highlight) {
        const [x1, y1] = this.dataToScreen(a.topLeft.x, a.topLeft.y);
        const [x2, y2] = this.dataToScreen(a.bottomRight.x, a.bottomRight.y);
        const rx = Math.min(x1, x2);
        const ry = Math.min(y1, y2);
        const rw = Math.abs(x2 - x1);
        const rh = Math.abs(y2 - y1);

        ctx.save();
        if (highlight) { ctx.shadowColor = '#1976d2'; ctx.shadowBlur = 6; }

        ctx.fillStyle = this._withAlpha(a.fillColor, a.fillOpacity);
        ctx.fillRect(rx, ry, rw, rh);
        ctx.strokeStyle = a.strokeColor;
        ctx.lineWidth = highlight ? a.strokeWidth + 2 : a.strokeWidth;
        ctx.strokeRect(rx, ry, rw, rh);
        ctx.restore();
    }

    // ---- Drawing preview (dashed) ----
    _drawPreview(ctx, state) {
        const { tool, startData, currentData } = state;
        const [sx, sy] = this.dataToScreen(startData.x, startData.y);
        const [cx, cy] = this.dataToScreen(currentData.x, currentData.y);

        ctx.save();
        ctx.setLineDash([6, 4]);
        ctx.strokeStyle = this.config.defaults.stroke_color;
        ctx.lineWidth = this.config.defaults.stroke_width;
        ctx.globalAlpha = 0.6;

        if (tool === 'arrow') {
            ctx.beginPath();
            ctx.moveTo(sx, sy);
            ctx.lineTo(cx, cy);
            ctx.stroke();
            // Preview arrowhead
            const angle = Math.atan2(cy - sy, cx - sx);
            const headLen = 10;
            ctx.setLineDash([]);
            ctx.fillStyle = this.config.defaults.stroke_color;
            ctx.beginPath();
            ctx.moveTo(cx, cy);
            ctx.lineTo(cx - headLen * Math.cos(angle - Math.PI / 6), cy - headLen * Math.sin(angle - Math.PI / 6));
            ctx.lineTo(cx - headLen * Math.cos(angle + Math.PI / 6), cy - headLen * Math.sin(angle + Math.PI / 6));
            ctx.closePath();
            ctx.fill();
        } else if (tool === 'circle') {
            const r = Math.hypot(cx - sx, cy - sy);
            ctx.beginPath();
            ctx.arc(sx, sy, r, 0, Math.PI * 2);
            ctx.fillStyle = this._withAlpha(this.config.defaults.stroke_color, this.config.defaults.fill_opacity * 0.5);
            ctx.fill();
            ctx.stroke();
        } else if (tool === 'rectangle') {
            const rx = Math.min(sx, cx);
            const ry = Math.min(sy, cy);
            const rw = Math.abs(cx - sx);
            const rh = Math.abs(cy - sy);
            ctx.fillStyle = this._withAlpha(this.config.defaults.stroke_color, this.config.defaults.fill_opacity * 0.5);
            ctx.fillRect(rx, ry, rw, rh);
            ctx.strokeRect(rx, ry, rw, rh);
        }

        ctx.restore();
    }

    // ------------------------------------------------------------------
    //  Color helpers
    // ------------------------------------------------------------------

    _hexToRgba(hex) {
        const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        return m ? { r: parseInt(m[1], 16), g: parseInt(m[2], 16), b: parseInt(m[3], 16) } : { r: 0, g: 0, b: 0 };
    }

    _withAlpha(hex, alpha) {
        const { r, g, b } = this._hexToRgba(hex);
        return `rgba(${r},${g},${b},${alpha})`;
    }

    // ------------------------------------------------------------------
    //  Actions  (delete / clear / export / import)
    // ------------------------------------------------------------------

    handleAction(action) {
        if (action === 'delete' && this.selectedAnnotation) {
            this.deleteAnnotation(this.selectedAnnotation.id);
        } else if (action === 'clear') {
            this.clearAnnotations();
        } else if (action === 'export') {
            this.exportAnnotations();
        } else if (action === 'import') {
            const input = document.getElementById(`${this.containerId}-import-file`);
            if (input) input.click();
        }
    }

    exportAnnotations() {
        const payload = {
            version: '1.0',
            created: new Date().toISOString(),
            annotations: this.annotations.map(a => a.toJSON()),
        };
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `annotations-${Date.now()}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }

    handleImport(e) {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (ev) => {
            try {
                const data = JSON.parse(ev.target.result);
                if (data.annotations) this.loadAnnotations(data.annotations);
            } catch (err) {
                console.error('Annotation import failed', err);
                alert('Failed to import annotations: ' + err.message);
            }
        };
        reader.readAsText(file);
        // Reset file input so importing the same file again works
        e.target.value = '';
    }

    loadAnnotations(annotationData) {
        this.annotations = [];
        for (const d of annotationData) {
            let a;
            if (d.type === 'text')      a = new TextAnnotation(d.id, d.position, d.text, d);
            if (d.type === 'arrow')     a = new ArrowAnnotation(d.id, d.start, d.end, d);
            if (d.type === 'circle')    a = new CircleAnnotation(d.id, d.center, d.radius, d);
            if (d.type === 'rectangle') a = new RectangleAnnotation(d.id, d.topLeft, d.bottomRight, d);
            if (a) this.annotations.push(a);
        }
        this.updateAnnotationList();
        this.redraw();
    }

    // ------------------------------------------------------------------
    //  Cleanup
    // ------------------------------------------------------------------

    destroy() {
        // Remove canvas
        if (this.canvas && this.canvas.parentNode) this.canvas.parentNode.removeChild(this.canvas);

        // Disconnect resize observer
        if (this._resizeObserver) this._resizeObserver.disconnect();

        // Restore original viewstate handler
        if (this._origOnViewStateChange !== undefined) {
            this.datamap.deckgl.setProps({ onViewStateChange: this._origOnViewStateChange || undefined });
        }

        // Restore deck.gl controller
        this.datamap.deckgl.setProps({
            controller: { scrollZoom: { speed: 0.01, smooth: true }, dragPan: true, dragRotate: true },
            getCursor: ({ isDragging }) => isDragging ? 'grabbing' : 'grab',
        });

        // Remove window listeners
        window.removeEventListener('mousedown', this._onMouseDown);
        window.removeEventListener('mousemove', this._onMouseMove);
        window.removeEventListener('mouseup', this._onMouseUp);
        window.removeEventListener('keydown', this._onKeyDown);

        // Remove inline text input
        this._removeTextInput();

        // Cancel pending animation frame
        if (this._rafId) { cancelAnimationFrame(this._rafId); this._rafId = null; }
    }
}
