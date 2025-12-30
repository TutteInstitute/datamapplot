/**
 * DataMapPlot Initialization Script
 * 
 * This script handles the initialization and data loading for interactive DataMapPlot visualizations.
 * It includes utilities for debouncing, Arrow data parsing, progress tracking, and loading various data layers.
 */

// =============================================================================
// Utility Functions
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

// =============================================================================
// DataMapPlot Initialization Class
// =============================================================================

/**
 * Class to manage DataMapPlot initialization and data loading.
 */
class DataMapPlotInitializer {
    /**
     * Create a new DataMapPlotInitializer.
     * @param {Object} config - Configuration object
     */
    constructor(config) {
        this.config = config;
        this.datamap = null;
        this.workers = {};
        this.workerUrl = null;
    }

    /**
     * Initialize the DataMap and start loading data.
     */
    async initialize() {
        // Verify Compression Streams API support
        if (!("CompressionStream" in window)) {
            throw new Error(
                "Your browser doesn't support the Compression Streams API " +
                "https://developer.mozilla.org/docs/Web/API/Compression_Streams_API#browser_compatibility"
            );
        }

        // Create the DataMap instance
        this.datamap = new DataMap({
            container: this.config.container,
            bounds: this.config.dataBounds,
            searchItemId: this.config.searchItemId,
            lassoSelectionItemId: this.config.selectionItemId,
        });

        // Create workers
        this.workerUrl = this._createWorkerBlob();
        
        // Load data layers
        await this._loadAllData();

        return this.datamap;
    }

    /**
     * Create the web worker blob URL.
     * @returns {string} - Blob URL for the worker
     * @private
     */
    _createWorkerBlob() {
        // This will be set by the template based on inline_data config
        const workerCode = this.config.workerCode;
        const blob = new Blob([workerCode], { type: 'application/javascript' });
        return URL.createObjectURL(blob);
    }

    /**
     * Load all data layers.
     * @private
     */
    async _loadAllData() {
        // Load in parallel where possible
        this._loadPointDataLayer();
        this._loadLabelDataLayer();
        this._loadMetaData();

        if (this.config.enableHistogram) {
            this._loadHistogramData();
        }

        if (this.config.backgroundImage) {
            this.datamap.addBackgroundImage(
                this.config.backgroundImage,
                this.config.backgroundImageBounds
            );
        }

        if (this.config.enableApiTooltip) {
            this._setupDynamicTooltip();
        }
    }

    /**
     * Load point data layer.
     * @private
     */
    _loadPointDataLayer() {
        const pointDataWorker = new Worker(this.workerUrl);
        pointDataWorker.postMessage({
            encodedData: this.config.pointDataEncoded,
            JSONParse: false
        });

        pointDataWorker.onmessage = async (event) => {
            if (event.data.type === "progress") {
                updateProgressBar('point-data-progress', event.data.progress);
            } else {
                const { data } = event.data;
                let pointData;
                
                if (this.config.inlineData) {
                    pointData = await simpleArrowParser(data);
                } else {
                    const chunkArray = data.map(async ({ chunkIndex, chunkData }) => {
                        return {chunkIndex, chunkData: await simpleArrowParser(chunkData)};
                    });
                    pointData = await Promise.all(chunkArray).then(combineTypedTableChunks);
                }

                this.datamap.addPoints(pointData, this.config.pointOptions);

                document.getElementById("loading").style.display = "none";
                updateProgressBar('point-data-progress', 100);
                checkAllDataLoaded();

                if (this.config.enableLassoSelection) {
                    const lassoSelector = new LassoSelectionTool(this.datamap);
                    this.datamap.lassoSelector = lassoSelector;
                }
            }
        };

        // Load colormap data if enabled
        if (this.config.enableColormapSelector) {
            this._loadColorData();
        }

        // Load edge data if enabled
        if (this.config.edgeBundle) {
            this._loadEdgeData();
        }
    }

    /**
     * Load colormap data.
     * @private
     */
    _loadColorData() {
        const colorDataWorker = new Worker(this.workerUrl);
        colorDataWorker.postMessage({
            encodedData: this.config.colorDataEncoded,
            JSONParse: false
        });

        colorDataWorker.onmessage = async (event) => {
            if (event.data.type === "progress") {
                updateProgressBar('color-data-progress', event.data.progress);
            } else {
                const { data } = event.data;
                let colorData;

                if (this.config.inlineData) {
                    colorData = await simpleArrowParser(data);
                } else {
                    const chunkArray = data.map(async ({ chunkIndex, chunkData }) => {
                        return {chunkIndex, chunkData: await simpleArrowParser(chunkData)};
                    });
                    colorData = await Promise.all(chunkArray).then(combineTypedTableChunks);
                }

                updateProgressBar('color-data-progress', 100);
                checkAllDataLoaded();

                const colorMapContainer = document.getElementById("colormap-selector-container");
                const legendContainer = document.getElementById("legend-container");

                const colorSelector = new ColormapSelectorTool(
                    this.config.colormapMetadata,
                    colorMapContainer,
                    colorData,
                    legendContainer,
                    this.datamap,
                );
                this.datamap.colorSelector = colorSelector;
            }
        };
    }

    /**
     * Load edge bundle data.
     * @private
     */
    _loadEdgeData() {
        const edgeDataWorker = new Worker(this.workerUrl);
        edgeDataWorker.postMessage({
            encodedData: this.config.edgeDataEncoded,
            JSONParse: false
        });

        edgeDataWorker.onmessage = async (event) => {
            if (event.data.type === "progress") {
                updateProgressBar('edge-data-progress', event.data.progress);
            } else {
                const { data } = event.data;
                let edgeData;

                if (this.config.inlineData) {
                    edgeData = await simpleArrowParser(data);
                } else {
                    const chunkArray = data.map(async ({ chunkIndex, chunkData }) => {
                        return {chunkIndex, chunkData: await simpleArrowParser(chunkData)};
                    });
                    edgeData = await Promise.all(chunkArray).then(combineTypedTableChunks);
                }

                this.datamap.addEdges(edgeData, {
                    edgeWidth: this.config.edgeWidth,
                });

                updateProgressBar('edge-data-progress', 100);
                checkAllDataLoaded();
            }
        };
    }

    /**
     * Load label data layer.
     * @private
     */
    _loadLabelDataLayer() {
        const labelDataWorker = new Worker(this.workerUrl);
        labelDataWorker.postMessage({
            encodedData: this.config.labelDataEncoded,
            JSONParse: true
        });

        labelDataWorker.onmessage = async (event) => {
            if (event.data.type === "progress") {
                updateProgressBar('label-data-progress', event.data.progress);
            } else {
                const { data } = event.data;
                const labelData = this.config.inlineData ? data : data[0].chunkData;
                
                this.datamap.labelData = labelData;

                // Filter labels for topic tree if enabled
                const labelsToAdd = this.config.enableTopicTree
                    ? labelData.filter((d) => !(d.id && d.id.endsWith('-1')))
                    : labelData;

                this.datamap.addLabels(labelsToAdd, this.config.labelOptions);

                if (this.config.enableTopicTree) {
                    this._setupTopicTree(labelData);
                }

                if (this.config.clusterBoundaryPolygons) {
                    this.datamap.addBoundaries(
                        labelData.filter((d) => d.polygon),
                        { clusterBoundaryLineWidth: this.config.clusterBoundaryLineWidth }
                    );
                }

                document.getElementById("loading").style.display = "none";
                updateProgressBar('label-data-progress', 100);
                checkAllDataLoaded();
            }
        };
    }

    /**
     * Setup the topic tree component.
     * @param {Array} labelData - The label data
     * @private
     */
    _setupTopicTree(labelData) {
        const topicTreeContainer = document.querySelector('#topic-tree');
        
        const topicTree = new TopicTree(
            topicTreeContainer,
            this.datamap,
            !!this.config.topicTreeButtonOnClick,
            this.config.topicTreeButtonIcon,
            this.config.topicTreeOptions
        );

        if (this.config.topicTreeButtonOnClick) {
            topicTree.container.querySelectorAll('.topic-tree-btn').forEach(button => {
                button.addEventListener('click', function() {
                    const label = this.datamap.labelData.find(l => l.id === this.dataset.labelId);
                    // Execute the custom click handler
                    this.config.topicTreeButtonOnClick(label);
                }.bind(this));
            });
        }

        const debouncedViewStateChange = debounce(({viewState, interactionState}) => {
            const userIsInteracting = Object.values(interactionState).every(Boolean);
            if (!userIsInteracting) {
                const visible = getVisibleTextData(viewState, this.datamap.labelData);
                if (visible) {
                    topicTree.highlightElements(visible);
                }
            }
        }, 150);

        this.datamap.deckgl.setProps({
            onViewStateChange: debouncedViewStateChange,
        });
    }

    /**
     * Load metadata (hover data).
     * @private
     */
    _loadMetaData() {
        const metaDataWorker = new Worker(this.workerUrl);
        metaDataWorker.postMessage({
            encodedData: this.config.hoverDataEncoded,
            JSONParse: true
        });

        metaDataWorker.onmessage = async (event) => {
            if (event.data.type === "progress") {
                updateProgressBar('meta-data-progress', event.data.progress);
            } else {
                const { data } = event.data;
                const hoverData = this.config.inlineData ? data : combineTableChunks(data);

                this.datamap.addMetaData(hoverData, {
                    tooltipFunction: this.config.getTooltip,
                    onClickFunction: this.config.onClick,
                    searchField: this.config.searchField,
                });

                if (this.config.enableSearch) {
                    const searchItem = document.getElementById(this.config.searchItemId);
                    if (searchItem) {
                        searchItem.addEventListener("input", 
                            debounce(event => this.datamap.searchText(event.target.value))
                        );
                    }
                }

                updateProgressBar('meta-data-progress', 100);
                checkAllDataLoaded();
            }
        };
    }

    /**
     * Load histogram data.
     * @private
     */
    async _loadHistogramData() {
        const chartSelectionCallback = chartSelectedIndices => {
            if (chartSelectedIndices === null) {
                this.datamap.removeSelection(this.config.histogramItemId);
            } else {
                this.datamap.addSelection(chartSelectedIndices, this.config.histogramItemId);
            }
        };

        const [histogramBinData, histogramIndexData] = await Promise.all([
            this._loadHistogramBinData(),
            this._loadHistogramIndexData()
        ]);

        const histogramData = {
            rawBinData: histogramBinData,
            rawIndexData: histogramIndexData
        };

        const histogramItem = D3Histogram.create({
            data: histogramData,
            chartContainerId: this.config.histogramItemId,
            ...this.config.histogramOptions,
            chartSelectionCallback: chartSelectionCallback,
        });

        this.datamap.connectHistogram(histogramItem);
    }

    /**
     * Load histogram bin data.
     * @returns {Promise<Object>} - The histogram bin data
     * @private
     */
    _loadHistogramBinData() {
        return new Promise((resolve, reject) => {
            const histogramBinDataWorker = new Worker(this.workerUrl);
            histogramBinDataWorker.postMessage({
                encodedData: this.config.histogramBinDataEncoded,
                JSONParse: true
            });

            histogramBinDataWorker.onmessage = async (event) => {
                if (event.data.type === "progress") {
                    updateProgressBar('histogram-bin-data-progress', event.data.progress);
                } else {
                    const { data } = event.data;
                    const histogramBinData = this.config.inlineData ? data : data[0].chunkData;
                    updateProgressBar('histogram-bin-data-progress', 100);
                    checkAllDataLoaded();
                    resolve(histogramBinData);
                }
            };
        });
    }

    /**
     * Load histogram index data.
     * @returns {Promise<Object>} - The histogram index data
     * @private
     */
    _loadHistogramIndexData() {
        return new Promise((resolve, reject) => {
            const histogramIndexDataWorker = new Worker(this.workerUrl);
            histogramIndexDataWorker.postMessage({
                encodedData: this.config.histogramIndexDataEncoded,
                JSONParse: false
            });

            histogramIndexDataWorker.onmessage = async (event) => {
                if (event.data.type === "progress") {
                    updateProgressBar('histogram-index-data-progress', event.data.progress);
                } else {
                    const { data } = event.data;
                    const rawData = this.config.inlineData ? data : data[0].chunkData;
                    const histogramIndexData = await simpleArrowParser(rawData);
                    updateProgressBar('histogram-index-data-progress', 100);
                    checkAllDataLoaded();
                    resolve(histogramIndexData);
                }
            };
        });
    }

    /**
     * Setup dynamic tooltip functionality.
     * @private
     */
    _setupDynamicTooltip() {
        const tooltip = new DynamicTooltipManager(
            this.datamap,
            this.config.tooltipOptions
        );
    }
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        debounce,
        simpleArrowParser,
        mergeTypedArrays,
        combineTypedTableChunks,
        combineTableChunks,
        updateProgressBar,
        checkAllDataLoaded,
        isBoundsVisible,
        getVisibleTextData,
        DataMapPlotInitializer
    };
}
