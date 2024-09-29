/**
 * Represents a rectangle in 2D space.
 * @typedef {Object} Rect
 * @property {number} x - The x-coordinate of the top-left corner.
 * @property {number} y - The y-coordinate of the top-left corner.
 * @property {number} width - The width of the rectangle.
 * @property {number} height - The height of the rectangle.
 */

/**
 * This function pushes all elements of the input array into the array that called it.
 * @param {Array} other 
 */
Array.prototype.pushAll = function(other) {
    if (other.length < 16384) {
        this.push(...other);
    } else {
        for (let i = 0; i < other.length; i++) {
            this.push(other[i]);
        }
    }
}

/**
 * A QuadTree implementation for efficient spatial partitioning and querying.
 */
class QuadTree {
    /**
     * Creates a new QuadTree instance.
     * @param {Rect} boundary - The boundary of this quad.
     * @param {number} capacity - The maximum number of points a leaf node can hold before splitting.
     */
    constructor(boundary, capacity) {
        this.boundary = boundary;
        this.capacity = capacity;
        this.points = [];
        this.divided = false;
    }

    /**
     * Subdivides the current quad into four sub-quads.
     */
    subdivide() {
        const x = this.boundary.x;
        const y = this.boundary.y;
        const w = this.boundary.width / 2;
        const h = this.boundary.height / 2;

        const ne = new QuadTree({ x: x + w, y: y, width: w, height: h }, this.capacity);
        const nw = new QuadTree({ x: x, y: y, width: w, height: h }, this.capacity);
        const se = new QuadTree({ x: x + w, y: y + h, width: w, height: h }, this.capacity);
        const sw = new QuadTree({ x: x, y: y + h, width: w, height: h }, this.capacity);

        this.northeast = ne;
        this.northwest = nw;
        this.southeast = se;
        this.southwest = sw;

        this.divided = true;
    }

    /**
     * Inserts a point into the QuadTree.
     * @param {Float32Array} points - The Float32Array containing all points.
     * @param {number} index - The index of the point in the Float32Array.
     * @returns {boolean} True if the point was inserted successfully, false otherwise.
     */
    insert(points, index) {
        const x = points[index * 2];
        const y = points[index * 2 + 1];

        if (!this.containsPoint(x, y)) {
            return false;
        }

        if (this.points.length < this.capacity) {
            this.points.push(index);
            return true;
        }

        if (!this.divided) {
            this.subdivide();
        }

        return (this.northeast.insert(points, index) || this.northwest.insert(points, index) ||
            this.southeast.insert(points, index) || this.southwest.insert(points, index));
    }

    /**
     * Queries the QuadTree for points within a given range.
     * @param {Rect} range - The range to query.
     * @param {Float32Array} points - The Float32Array containing all points.
     * @returns {number[]} An array of indices of points within the given range.
     */
    query(range, points) {
        const found = [];

        if (!this.intersects(range)) {
            return found;
        }

        for (const index of this.points) {
            const x = points[index * 2];
            const y = points[index * 2 + 1];
            if (this.rangeContainsPoint(range, x, y)) {
                found.push(index);
            }
        }

        if (this.divided) {
            found.pushAll(this.northeast.query(range, points));
            found.pushAll(this.northwest.query(range, points));
            found.pushAll(this.southeast.query(range, points));
            found.pushAll(this.southwest.query(range, points));
        }

        return found;
    }

    /**
     * Checks if a point is within the boundary of this quad.
     * @param {number} x - The x-coordinate of the point.
     * @param {number} y - The y-coordinate of the point.
     * @returns {boolean} True if the point is within the boundary, false otherwise.
     */
    containsPoint(x, y) {
        return (x >= this.boundary.x && x < this.boundary.x + this.boundary.width &&
            y >= this.boundary.y && y < this.boundary.y + this.boundary.height);
    }

    /**
     * Checks if this quad's boundary intersects with the given range.
     * @param {Rect} range - The range to check intersection with.
     * @returns {boolean} True if there's an intersection, false otherwise.
     */
    intersects(range) {
        return !(range.x > this.boundary.x + this.boundary.width ||
            range.x + range.width < this.boundary.x ||
            range.y > this.boundary.y + this.boundary.height ||
            range.y + range.height < this.boundary.y);
    }

    /**
     * Checks if a point is within the given range.
     * @param {Rect} range - The range to check.
     * @param {number} x - The x-coordinate of the point.
     * @param {number} y - The y-coordinate of the point.
     * @returns {boolean} True if the point is within the range, false otherwise.
     */
    rangeContainsPoint(range, x, y) {
        return (x >= range.x && x < range.x + range.width &&
            y >= range.y && y < range.y + range.height);
    }
}