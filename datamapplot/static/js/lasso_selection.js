/**
 * LassoSelectionTool class for implementing lasso selection functionality in a deck.gl application.
 * This tool allows users to select points on a scatter plot by drawing a lasso around them.
 */
class LassoSelectionTool {
    /**
     * Creates an instance of LassoSelectionTool.
     * @param {HTMLElement} container - The container element for the deck.gl application.
     * @param {Object} deckgl - The deck.gl instance.
     * @param {Object} dataSelectionManager - The data selection manager object.
     * @param {string} selectionItemId - The ID for the selection item.
     * @param {Function} selectPoints - Callback to select points in deckgl and histogram
     * @param {Function} handleSelectedPoints - Callback function to handle selected points.
     */
    constructor(
        container,
        deckgl,
        dataSelectionManager,
        selectionItemId,
        selectPoints,
        handleSelectedPoints
    ) {
        this.container = container;
        this.deckgl = deckgl;
        this.dataSelectionManager = dataSelectionManager;
        this.selectionItemId = selectionItemId;
        this.selectPoints = selectPoints;
        this.handleSelectedPoints = handleSelectedPoints;

        this.selectionMode = false;
        this.lassoPolygon = [];

        this.initCanvas();
        this.initEventListeners();
    }

    /**
     * Initializes the canvas for drawing the lasso.
     * @private
     */
    initCanvas() {
        this.canvas = document.createElement('canvas');
        this.canvas.width = this.container.clientWidth;
        this.canvas.height = this.container.clientHeight;
        this.canvas.style.position = 'absolute';
        this.canvas.style.top = '0';
        this.canvas.style.left = '0';
        this.canvas.style.pointerEvents = 'none';
        this.canvas.style.zIndex = '1000';
        document.body.appendChild(this.canvas);
        this.ctx = this.canvas.getContext('2d');
    }

    /**
     * Draws the lasso on the canvas.
     * @param {Array<Object>} lassoPolygon - Array of points forming the lasso polygon.
     */
    drawLasso(lassoPolygon) {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        this.ctx.beginPath();

        lassoPolygon.forEach(({ x, y }, index) => {
            const [screenX, screenY] = this.deckgl.viewManager.getViewports()[0].project([x, y]);
            if (index === 0) {
                this.ctx.moveTo(screenX, screenY);
            } else {
                this.ctx.lineTo(screenX, screenY);
            }
        });

        this.ctx.closePath();

        this.ctx.lineWidth = 2;
        this.ctx.strokeStyle = 'rgba(0, 128, 255, 0.8)';
        this.ctx.stroke();

        this.ctx.fillStyle = 'rgba(0, 128, 255, 0.1)';
        this.ctx.fill();
    }

    /**
     * Handles the selection of points.
     * @param {Array<number>} selectedPoints - Array of indices of selected points.
     */
    handleSelection(selectedPoints) {
        if (selectedPoints.length === 0) {
            this.dataSelectionManager.removeSelectedIndicesOfItem(this.selectionItemId);
        } else {
            this.dataSelectionManager.addOrUpdateSelectedIndicesOfItem(selectedPoints, this.selectionItemId);
        }
        this.selectPoints(this.selectionItemId);
        this.handleSelectedPoints(selectedPoints);
    }

    /**
     * Processes the completed lasso selection.
     * @param {Array<Object>} lassoPolygon - Array of points forming the lasso polygon.
     */
    onLassoComplete(lassoPolygon) {
        const selectedPoints = [];
        let currentSelectedIndices = this.dataSelectionManager.getSelectedIndices();
        if (this.dataSelectionManager.selectedIndicesByItem[this.selectionItemId]) {
            const otherSelectionItems = Object.keys(this.dataSelectionManager.selectedIndicesByItem)
                .filter(key => key !== this.selectionItemId);
            if (otherSelectionItems.length > 0) {
                currentSelectedIndices = this.dataSelectionManager.selectedIndicesByItem[otherSelectionItems[0]];
                for (let i = 1; i < otherSelectionItems.length; i++) {
                    const otherSelection = this.dataSelectionManager.selectedIndicesByItem[otherSelectionItems[i]];
                    currentSelectedIndices = currentSelectedIndices.intersection(otherSelection);
                }
            } else {
                currentSelectedIndices = new Set();
            }
        }
        const selectFromAllPoints = currentSelectedIndices.size === 0;

        this.deckgl.props.layers.forEach(layer => {
            if (layer instanceof deck.ScatterplotLayer) {
                const { attributes } = layer.props.data;
                const positions = attributes.getPosition.value;

                if (selectFromAllPoints) {
                    for (let i = 0; i < positions.length; i += 2) {
                        const point = { x: positions[i], y: positions[i + 1] };
                        if (this.isPointInPolygon(point, lassoPolygon)) {
                            selectedPoints.push((i / 2) >> 0);
                        }
                    }
                } else {
                    currentSelectedIndices.forEach(index => {
                        const point = { x: positions[index * 2], y: positions[index * 2 + 1] };
                        if (this.isPointInPolygon(point, lassoPolygon)) {
                            selectedPoints.push(index);
                        }
                    });
                }
            }
        });

        this.handleSelection(selectedPoints);
    }

    /**
     * Checks if a point is inside a polygon using the ray-casting algorithm.
     * @param {Object} point - The point to check.
     * @param {Array<Object>} polygon - The polygon to check against.
     * @returns {boolean} True if the point is inside the polygon, false otherwise.
     */
    isPointInPolygon(point, polygon) {
        let isInside = false;
        const { x, y } = point;

        for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
            const xi = polygon[i].x, yi = polygon[i].y;
            const xj = polygon[j].x, yj = polygon[j].y;

            const intersect = ((yi > y) !== (yj > y)) &&
                (x < (xj - xi) * (y - yi) / (yj - yi) + xi);
            if (intersect) isInside = !isInside;
        }

        return isInside;
    }

    /**
     * Sets the selection mode on or off.
     * @param {boolean} enabled - Whether to enable or disable selection mode.
     */
    setSelectionMode(enabled) {
        this.selectionMode = enabled;

        this.deckgl.setProps({
            controller: {
                dragPan: !this.selectionMode,
                dragRotate: !this.selectionMode,
            }
        });

        if (!enabled) {
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        }
    }

    /**
     * Converts screen coordinates to spatial coordinates.
     * @param {number} screenX - The x-coordinate on the screen.
     * @param {number} screenY - The y-coordinate on the screen.
     * @returns {Array<number>} The spatial coordinates [x, y].
     */
    getSpatialCoordinates(screenX, screenY) {
        const viewport = this.deckgl.viewManager.getViewports()[0];
        return viewport.unproject([screenX, screenY]);
    }

    /**
     * Initializes all event listeners for the lasso selection tool.
     * @private
     */
    initEventListeners() {
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Shift' && !this.selectionMode) {
                this.setSelectionMode(true);
            }
        });

        document.addEventListener('keyup', (e) => {
            if (e.key === 'Shift' && this.selectionMode) {
                this.setSelectionMode(false);
            }
        });

        this.container.addEventListener('mousedown', (e) => {
            if (this.selectionMode) {
                const [x, y] = this.getSpatialCoordinates(e.clientX, e.clientY);
                this.lassoPolygon = [{ x, y }];
            }
        });

        this.container.addEventListener('mousemove', (e) => {
            if (this.selectionMode && this.lassoPolygon.length > 0) {
                const [x, y] = this.getSpatialCoordinates(e.clientX, e.clientY);
                this.lassoPolygon.push({ x, y });
                this.drawLasso(this.lassoPolygon);
            }
        });

        this.container.addEventListener('mouseup', (e) => {
            if (this.selectionMode && this.lassoPolygon.length > 0) {
                const [x, y] = this.getSpatialCoordinates(e.clientX, e.clientY);
                this.lassoPolygon.push({ x, y });
                this.onLassoComplete(this.lassoPolygon);
                this.lassoPolygon = [];
            }
        });
    }
}