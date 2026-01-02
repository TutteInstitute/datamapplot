/**
 * DataMapPlot Utility Functions
 * 
 * Pure utility functions for interactive DataMapPlot visualizations.
 * These can be included directly in templates or loaded as a module.
 */

// =============================================================================
// General Utilities
// =============================================================================

/**
 * Debounce function to limit the rate at which a function can fire.
 * @param {Function} func - The function to debounce
 * @param {number} timeout - The debounce delay in milliseconds
 * @returns {Function} - The debounced function
 */
function debounce(func, timeout = 250) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => { func.apply(this, args); }, timeout);
    };
}

// =============================================================================
// Data Parsing Utilities
// =============================================================================

/**
 * Parse Apache Arrow IPC data into a JavaScript object.
 * @param {Uint8Array} arrow_bytes - The Arrow data as bytes
 * @returns {Promise<Object>} - Object with column names as keys and arrays as values
 */
async function simpleArrowParser(arrow_bytes) {
    const table = await Arrow.tableFromIPC(arrow_bytes);
    const result = {};
    table.schema.fields.forEach((field) => {
        result[field.name] = table.getChild(field.name).toArray();
    });
    return result;
}

/**
 * Merge multiple typed arrays into a single typed array.
 * @param {Array<TypedArray>} arrays - Array of typed arrays to merge
 * @returns {TypedArray} - Merged typed array
 */
function mergeTypedArrays(arrays) {
    let totalLength = arrays.reduce((acc, arr) => acc + arr.length, 0);
    let result = new arrays[0].constructor(totalLength);
    let currentLength = 0;
    for (let arr of arrays) {
        result.set(arr, currentLength);
        currentLength += arr.length;
    }
    return result;
}

/**
 * Combine typed table chunks into a single table object (for non-inline data).
 * @param {Array<Object>} tableChunks - Array of chunk objects with chunkIndex and chunkData
 * @returns {Object} - Combined table with merged typed arrays
 */
function combineTypedTableChunks(tableChunks) {
    tableChunks.sort((a, b) => a.chunkIndex - b.chunkIndex);
    const combinedTable = {};
    Object.keys(tableChunks[0].chunkData).forEach((key) => {
        const arrays = tableChunks.map((chunk) => chunk.chunkData[key]);
        combinedTable[key] = mergeTypedArrays(arrays);
    });
    return combinedTable;
}

/**
 * Combine regular table chunks into a single table object (for non-inline data).
 * @param {Array<Object>} tableChunks - Array of chunk objects with chunkIndex and chunkData
 * @returns {Object} - Combined table with concatenated arrays
 */
function combineTableChunks(tableChunks) {
    tableChunks.sort((a, b) => a.chunkIndex - b.chunkIndex);
    const combinedTable = {};
    Object.keys(tableChunks[0].chunkData).forEach((key) => {
        const arrays = tableChunks.map((chunk) => chunk.chunkData[key]);
        combinedTable[key] = arrays.flat();
    });
    return combinedTable;
}

// =============================================================================
// Progress Bar Management
// =============================================================================

/**
 * Update a progress bar element.
 * @param {string} id - The ID of the progress bar container
 * @param {number} progress - The progress percentage (0-100)
 */
function updateProgressBar(id, progress) {
    const progressBar = document.querySelector(`#${id} .datamapplot-progress-bar-fill`);
    const progressText = document.querySelector(`#${id} .datamapplot-progress-bar-text`);
    if (progressBar && progressText) {
        progressBar.style.width = `${progress}%`;
        progressText.textContent = `${id.replace('-progress', '').replace(/-/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}: ${progress}%`;
    }
}

/**
 * Check if all data has been loaded and hide loading indicators.
 */
function checkAllDataLoaded() {
    const progressBars = document.querySelectorAll('.datamapplot-progress-bar-fill');
    const allLoaded = Array.from(progressBars).every(bar => bar.style.width === '100%');
    if (allLoaded) {
        const loadingEl = document.getElementById("loading");
        const progressEl = document.getElementById("progress-container");
        if (loadingEl) loadingEl.style.display = "none";
        if (progressEl) progressEl.style.display = "none";
    }
}

// =============================================================================
// Topic Tree Utilities
// =============================================================================

/**
 * Check if a bounding box is visible in the current viewport.
 * @param {Object} params - Object containing bounds and viewState
 * @returns {boolean} - Whether the bounds are visible
 */
function isBoundsVisible({bounds, viewState}) {
    const {width, height, longitude, latitude, zoom} = viewState;

    const Viewport = new deck.WebMercatorViewport({
        width,
        height,
        longitude,
        latitude,
        zoom,
    });

    const minBounds = Viewport.project([bounds[0], bounds[2]]);
    const maxBounds = Viewport.project([bounds[1], bounds[3]]);

    return (
        ((minBounds[0] >= 0 && minBounds[0] <= width) || (maxBounds[0] >= 0 && maxBounds[0] <= width)) &&
        ((minBounds[1] >= 0 && minBounds[1] <= height) || (maxBounds[1] >= 0 && maxBounds[1] <= height))
    );
}

/**
 * Get label data that is currently visible in the viewport.
 * @param {Object} viewState - The current deck.gl view state
 * @param {Array} labelData - Array of label data objects
 * @returns {Array|undefined} - Filtered array of visible labels
 */
function getVisibleTextData(viewState, labelData) {
    if (labelData) {
        return labelData.filter((d) => {
            return isBoundsVisible({
                bounds: d.bounds,
                viewState: viewState,
            });
        });
    }
}
