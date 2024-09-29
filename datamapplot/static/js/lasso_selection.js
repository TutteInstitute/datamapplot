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
        datamap,
        handleSelectedPoints
    ) {
        this.datamap = datamap;
        this.handleSelectedPoints = handleSelectedPoints;
        this.itemId = datamap.lassoSelectionItemId;

        this.selectionMode = false;
        this.lassoPolygon = [];
        this.quadTree = null;
        this.points = null;

        this.initCanvas();
        this.initEventListeners();
        this.initQuadTree();
    }

    /**
    * Initializes the QuadTree with the current scatter plot data.
    */
    initQuadTree() {
        const scatterLayer = this.datamap.deckgl.props.layers.find(layer => layer instanceof deck.ScatterplotLayer);
        if (!scatterLayer) return;

        const { attributes } = scatterLayer.props.data;
        this.points = attributes.getPosition.value;

        // Find the bounds of the data
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        for (let i = 0; i < this.points.length; i += 2) {
            minX = Math.min(minX, this.points[i]);
            maxX = Math.max(maxX, this.points[i]);
            minY = Math.min(minY, this.points[i + 1]);
            maxY = Math.max(maxY, this.points[i + 1]);
        }

        // Estimate leaf size based on the number of points
        const numPoints = this.points.length / 2;
        const leafSize = Math.max(Math.ceil(Math.sqrt(numPoints)), 64);

        // Create the QuadTree
        const boundary = {
            x: minX,
            y: minY,
            width: maxX - minX,
            height: maxY - minY
        };
        this.quadTree = new QuadTree(boundary, leafSize);  // Capacity of 4 points per quad

        // Insert points into the QuadTree
        for (let i = 0; i < this.points.length / 2; i++) {
            this.quadTree.insert(this.points, i);
        }
    }


    /**
     * Initializes the canvas for drawing the lasso.
     * @private
     */
    initCanvas() {
        this.canvas = document.createElement('canvas');
        this.canvas.width = this.datamap.container.clientWidth;
        this.canvas.height = this.datamap.container.clientHeight;
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
            const [screenX, screenY] = this.datamap.deckgl.viewManager.getViewports()[0].project([x, y]);
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
            this.datamap.removeSelection(this.itemId);
        } else {
            this.datamap.addSelection(selectedPoints, this.itemId);
        }
        this.handleSelectedPoints(selectedPoints);
    }

    /**
     * Processes the completed lasso selection.
     * @param {Array<Object>} lassoPolygon - Array of points forming the lasso polygon.
     */
    onLassoComplete(lassoPolygon) {
        if (!this.quadTree || !this.points) return;

        // Find the bounds of the lasso
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        for (const point of lassoPolygon) {
          minX = Math.min(minX, point.x);
          maxX = Math.max(maxX, point.x);
          minY = Math.min(minY, point.y);
          maxY = Math.max(maxY, point.y);
        }
    
        // Query the QuadTree for points within the lasso bounds
        let potentialIndices = this.quadTree.query({
          x: minX,
          y: minY,
          width: maxX - minX,
          height: maxY - minY
        }, this.points);
    
        let selectedPoints = [];
        const currentSelectedIndices = this.datamap.dataSelectionManager.getBasicSelectedIndices();
        const selectFromAllPoints = currentSelectedIndices.size === 0;

        // Check which points are actually inside the lasso
        if (selectFromAllPoints) {
            selectedPoints = potentialIndices.filter(index => 
                this.isPointInPolygon({x: this.points[index * 2], y: this.points[index * 2 + 1]}, lassoPolygon)
            );
        } else {
            selectedPoints = potentialIndices.filter(index =>
                currentSelectedIndices.has(index) &&
                this.isPointInPolygon({x: this.points[index * 2], y: this.points[index * 2 + 1]}, lassoPolygon)
            );
        }

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

        this.datamap.deckgl.setProps({
            controller: {
                dragPan: !this.selectionMode,
                dragRotate: !this.selectionMode,
            },
            getCursor: ({isDragging}) => this.selectionMode ? "crosshair" : (isDragging ? "grabbing" : "grab"),
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
        const viewport = this.datamap.deckgl.viewManager.getViewports()[0];
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

        this.datamap.container.addEventListener('mousedown', (e) => {
            if (this.selectionMode) {
                const [x, y] = this.getSpatialCoordinates(e.clientX, e.clientY);
                this.lassoPolygon = [{ x, y }];
            }
        });

        this.datamap.container.addEventListener('mousemove', (e) => {
            if (this.selectionMode && this.lassoPolygon.length > 0) {
                const [x, y] = this.getSpatialCoordinates(e.clientX, e.clientY);
                this.lassoPolygon.push({ x, y });
                this.drawLasso(this.lassoPolygon);
            }
        });

        this.datamap.container.addEventListener('mouseup', (e) => {
            if (this.selectionMode && this.lassoPolygon.length > 0) {
                const [x, y] = this.getSpatialCoordinates(e.clientX, e.clientY);
                this.lassoPolygon.push({ x, y });
                this.onLassoComplete(this.lassoPolygon);
                this.lassoPolygon = [];
            }
        });
    }
}