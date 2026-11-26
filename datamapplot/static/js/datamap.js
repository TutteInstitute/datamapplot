
LAYER_ORDER = ['imageLayer', 'densityOverviewLayer', 'dataPointLayer', 'hexagonLayer', 'boundaryLayer', 'labelLayer'];

function getLayerIndex(object) {
  // Exact match first
  const idx = LAYER_ORDER.indexOf(object.id);
  if (idx !== -1) return idx;
  // Prefix match for multi-tile layers (e.g. 'densityOverviewLayer_L0_R0_C0')
  for (let i = 0; i < LAYER_ORDER.length; i++) {
    if (object.id.startsWith(LAYER_ORDER[i])) return i;
  }
  return -1;
}

/**
 * WidgetRegistry - A simple pub/sub system for widget communication
 * 
 * This registry allows widgets to:
 * - Register themselves with the datamap
 * - Subscribe to events from other widgets
 * - Publish events for other widgets to consume
 * - Access other registered widgets
 */
class WidgetRegistry {
  constructor() {
    this.widgets = new Map();
    this.eventHandlers = new Map();
  }

  /**
   * Register a widget with the registry
   * @param {string} widgetId - Unique identifier for the widget
   * @param {Object} widget - The widget instance or object
   */
  register(widgetId, widget) {
    this.widgets.set(widgetId, widget);
    this.emit('widget-registered', { widgetId, widget });
  }

  /**
   * Unregister a widget from the registry
   * @param {string} widgetId - The widget ID to remove
   */
  unregister(widgetId) {
    const widget = this.widgets.get(widgetId);
    if (widget) {
      this.widgets.delete(widgetId);
      this.emit('widget-unregistered', { widgetId, widget });
    }
  }

  /**
   * Get a registered widget by ID
   * @param {string} widgetId - The widget ID to retrieve
   * @returns {Object|undefined} The widget instance or undefined
   */
  get(widgetId) {
    return this.widgets.get(widgetId);
  }

  /**
   * Check if a widget is registered
   * @param {string} widgetId - The widget ID to check
   * @returns {boolean} True if the widget is registered
   */
  has(widgetId) {
    return this.widgets.has(widgetId);
  }

  /**
   * Get all registered widget IDs
   * @returns {Array<string>} Array of widget IDs
   */
  getWidgetIds() {
    return Array.from(this.widgets.keys());
  }

  /**
   * Subscribe to an event
   * @param {string} eventName - Name of the event to subscribe to
   * @param {Function} handler - Handler function to call when event occurs
   * @returns {Function} Unsubscribe function
   */
  on(eventName, handler) {
    if (!this.eventHandlers.has(eventName)) {
      this.eventHandlers.set(eventName, new Set());
    }
    this.eventHandlers.get(eventName).add(handler);

    // Return unsubscribe function
    return () => {
      const handlers = this.eventHandlers.get(eventName);
      if (handlers) {
        handlers.delete(handler);
      }
    };
  }

  /**
   * Subscribe to an event once
   * @param {string} eventName - Name of the event to subscribe to
   * @param {Function} handler - Handler function to call when event occurs
   */
  once(eventName, handler) {
    const wrappedHandler = (data) => {
      this.off(eventName, wrappedHandler);
      handler(data);
    };
    this.on(eventName, wrappedHandler);
  }

  /**
   * Unsubscribe from an event
   * @param {string} eventName - Name of the event
   * @param {Function} handler - Handler function to remove
   */
  off(eventName, handler) {
    const handlers = this.eventHandlers.get(eventName);
    if (handlers) {
      handlers.delete(handler);
    }
  }

  /**
   * Emit an event to all subscribers
   * @param {string} eventName - Name of the event to emit
   * @param {Object} data - Data to pass to event handlers
   */
  emit(eventName, data = {}) {
    const handlers = this.eventHandlers.get(eventName);
    if (handlers) {
      handlers.forEach(handler => {
        try {
          handler(data);
        } catch (error) {
          console.error(`Error in widget event handler for "${eventName}":`, error);
        }
      });
    }
  }

  /**
   * Clear all event handlers for a specific event
   * @param {string} eventName - Name of the event to clear
   */
  clearEvent(eventName) {
    this.eventHandlers.delete(eventName);
  }

  /**
   * Clear all registered widgets and events
   */
  clear() {
    this.widgets.clear();
    this.eventHandlers.clear();
  }
}

function isFontLoaded(fontName) {
  return document.fonts.check(`12px "${fontName}"`);
}

// Function to wait for a font to load
function waitForFont(fontName, maxWait = 500) {
  return new Promise((resolve, reject) => {
    if (isFontLoaded(fontName)) {
      resolve();
    } else {
      const startTime = Date.now();
      const interval = setInterval(() => {
        if (isFontLoaded(fontName)) {
          clearInterval(interval);
          resolve();
        } else if (Date.now() - startTime > maxWait) {
          clearInterval(interval);
          reject(new Error(`Font ${fontName} did not load within ${maxWait}ms`));
        }
      }, 50);
    }
  });
}

function getInitialViewportSize() {
  const width = document.documentElement.clientWidth;
  const height = document.documentElement.clientHeight;

  return { viewportWidth: width, viewportHeight: height };
}

function calculateZoomLevel(bounds, viewportWidth, viewportHeight, padding = 0.5) {
  // Calculate the range of the bounds
  const lngRange = bounds[1] - bounds[0];
  const latRange = bounds[3] - bounds[2];

  // Calculate the center of the bounds
  const centerLng = (bounds[0] + bounds[1]) / 2;
  const centerLat = (bounds[2] + bounds[3]) / 2;

  // Calculate the zoom level for both dimensions
  const zoomX = Math.log2(360 / (lngRange / (viewportWidth / 256)));
  const zoomY = Math.log2(180 / (latRange / (viewportHeight / 256)));

  const zoom = Math.min(zoomX, zoomY) - padding;

  return { zoomLevel: zoom, dataCenter: [centerLng, centerLat] };
}

class DataMap {
  constructor({
    container,
    bounds,
    searchItemId = "text-search",
    lassoSelectionItemId = "lasso-selection",
    scrollZoomSpeed = 0.01,
  }) {
    this.container = container;
    this.searchItemId = searchItemId;
    this.lassoSelectionItemId = lassoSelectionItemId;
    this.scrollZoomSpeed = scrollZoomSpeed;
    this.filterLabelsOnSearch = false;
    this.pointData = null;
    this.labelData = null;
    this.metaData = null;
    this.layers = [];
    // Layers owned by widgets (see setOverlayLayers), drawn with the map's own layers,
    // and how the map's own layers are shown meanwhile (see setBaseLayerDisplay).
    this._overlayLayers = new Map();
    this._overlayIds = [];
    this._baseDisplay = { points: true, others: 1 };
    // deck.gl controller options; interaction is disabled while any owner holds a lock.
    this._controllerOptions = { scrollZoom: { speed: this.scrollZoomSpeed, smooth: true } };
    this._interactionLocks = new Set();
    const { viewportWidth, viewportHeight } = getInitialViewportSize();
    const { zoomLevel, dataCenter } = calculateZoomLevel(bounds, viewportWidth, viewportHeight);
    this.deckgl = new deck.DeckGL({
      container: container,
      initialViewState: {
        latitude: dataCenter[1],
        longitude: dataCenter[0],
        zoom: zoomLevel
      },
      controller: { ...this._controllerOptions },
    });
    this.updateTriggerCounter = 0;
    this.dataSelectionManager = new DataSelectionManager(lassoSelectionItemId);

    // Widget registry for inter-widget communication
    this.widgetRegistry = new WidgetRegistry();

    // Centralised view-state-change and pointer-event dispatch.
    // A single permanent handler on deck.gl fans out to all registered
    // listeners, replacing the fragile capture-and-wrap chain pattern.
    this._viewStateListeners = new Map();
    this._hoverListeners = new Map();
    this._clickListeners = new Map();
    this._selectionListeners = new Map();
    this._pointColorsListeners = new Map();
    // Optional hook (info) => info applied to picks before hover/click/tooltip
    // handlers see them; lets layers that draw a subset of the points (e.g. the
    // re-embed widget) report indices into the full point data.
    this.pickRemap = null;
    this.deckgl.setProps({
      onViewStateChange: (params) => {
        for (const handler of this._viewStateListeners.values()) {
          try { handler(params); } catch (e) {
            console.error('Error in viewStateChange listener:', e);
          }
        }
        return params.viewState;
      },
      onHover: (info, event) => {
        if (this.pickRemap) info = this.pickRemap(info);
        for (const handler of this._hoverListeners.values()) {
          try { handler(info, event); } catch (e) {
            console.error('Error in hover listener:', e);
          }
        }
      },
      onClick: (info, event) => {
        if (this.pickRemap) info = this.pickRemap(info);
        for (const handler of this._clickListeners.values()) {
          try { handler(info, event); } catch (e) {
            console.error('Error in click listener:', e);
          }
        }
      },
    });
  }

  /**
   * Register a named view-state-change listener.
   * @param {string} id   Unique key (e.g. 'hexZoom', 'annotation').
   * @param {Function} handler  Called with the deck.gl onViewStateChange params.
   */
  onViewStateChange(id, handler) {
    this._viewStateListeners.set(id, handler);
  }

  /**
   * Remove a previously registered view-state-change listener by id.
   * @param {string} id  The key used when registering.
   */
  offViewStateChange(id) {
    this._viewStateListeners.delete(id);
  }

  /**
   * Programmatically trigger all view-state-change listeners.
   * deck.gl only fires onViewStateChange for user interactions, so call
   * this after setting initialViewState via setProps to keep every
   * subsystem (annotation overlay, minimap, hex zoom, etc.) in sync.
   * @param {Object} viewState  The new view state object.
   * @param {Object} [options]
   * @param {boolean} [options.force=false]  Recompute view-dependent layer state
   *   (e.g. the density overview crossfade) even if the zoom has not changed
   *   since it was last computed.
   */
  notifyViewStateChange(viewState, { force = false } = {}) {
    if (force) this._densityOverviewLastT = null;
    for (const handler of this._viewStateListeners.values()) {
      try { handler({ viewState }); } catch (e) {
        console.error('Error in viewStateChange listener:', e);
      }
    }
  }

  /**
   * Register a named hover listener, called on every deck.gl hover event.
   * @param {string} id   Unique key (e.g. 'dynamicTooltip', 'tapToInspect').
   * @param {Function} handler  Called with the deck.gl (info, event) pair.
   */
  onHover(id, handler) {
    this._hoverListeners.set(id, handler);
  }

  /**
   * Remove a previously registered hover listener by id.
   * @param {string} id  The key used when registering.
   */
  offHover(id) {
    this._hoverListeners.delete(id);
  }

  /**
   * Register a named click listener, called on every deck.gl click event.
   * @param {string} id   Unique key (e.g. 'metaDataOnClick', 'tapToInspect').
   * @param {Function} handler  Called with the deck.gl (info, event) pair.
   */
  onClick(id, handler) {
    this._clickListeners.set(id, handler);
  }

  /**
   * Remove a previously registered click listener by id.
   * @param {string} id  The key used when registering.
   */
  offClick(id) {
    this._clickListeners.delete(id);
  }

  /**
   * Register a named listener called after the selection (and with it each
   * point's selection state, see getPointSelectionState) changes.
   * @param {string} id   Unique key.
   * @param {Function} handler  Called with no arguments.
   */
  onSelectionChange(id, handler) {
    this._selectionListeners.set(id, handler);
  }

  /** Remove a selection-change listener by id. */
  offSelectionChange(id) {
    this._selectionListeners.delete(id);
  }

  /**
   * Register a named listener called after the point colours change (e.g. a
   * different colormap; see getPoints).
   * @param {string} id   Unique key.
   * @param {Function} handler  Called with no arguments.
   */
  onPointColorsChange(id, handler) {
    this._pointColorsListeners.set(id, handler);
  }

  /** Remove a point-colours-change listener by id. */
  offPointColorsChange(id) {
    this._pointColorsListeners.delete(id);
  }

  _emit(listeners, name) {
    for (const handler of listeners.values()) {
      try { handler(); } catch (e) {
        console.error(`Error in ${name} listener:`, e);
      }
    }
  }

  addPoints(pointData, {
    pointSize,
    pointOutlineColor = [250, 250, 250, 128],
    pointLineWidth = 0.001,
    pointHoverColor = [170, 0, 0, 187],
    pointLineWidthMaxPixels = 3,
    pointLineWidthMinPixels = 0.001,
    pointRadiusMaxPixels = 16,
    pointRadiusMinPixels = 0.2,
  }) {
    // Store point data for widget access
    this.pointData = pointData;

    // Parse out and reformat data for deck.gl
    const numPoints = pointData.x.length;
    const positions = new Float32Array(numPoints * 2);
    const colors = new Uint8Array(numPoints * 4);
    const variableSize = pointSize < 0;
    let sizes;
    if (variableSize) {
      sizes = new Float32Array(numPoints);
    } else {
      sizes = null;
    }

    // Populate the arrays
    for (let i = 0; i < numPoints; i++) {
      positions[i * 2] = pointData.x[i];
      positions[i * 2 + 1] = pointData.y[i];
      colors[i * 4] = pointData.r[i];
      colors[i * 4 + 1] = pointData.g[i];
      colors[i * 4 + 2] = pointData.b[i];
      colors[i * 4 + 3] = pointData.a[i];
      if (variableSize) {
        sizes[i] = pointData.size[i];
      }
    }
    this.originalColors = colors;
    this.selected = new Float32Array(numPoints).fill(1.0);
    this.pointSize = pointSize;
    this.pointOutlineColor = pointOutlineColor;
    this.pointLineWidth = pointLineWidth;
    this.pointHoverColor = pointHoverColor;
    this.pointLineWidthMaxPixels = pointLineWidthMaxPixels;
    this.pointLineWidthMinPixels = pointLineWidthMinPixels;
    this.pointRadiusMaxPixels = pointRadiusMaxPixels;
    this.pointRadiusMinPixels = pointRadiusMinPixels;

    let scatterAttributes = {
      getPosition: { value: positions, size: 2 },
      getFillColor: { value: colors, size: 4 },
      getFilterValue: { value: this.selected, size: 1 }
    };
    if (variableSize) {
      scatterAttributes.getRadius = { value: sizes, size: 1 };
    }

    this.pointLayer = new deck.ScatterplotLayer({
      id: 'dataPointLayer',
      data: {
        length: numPoints,
        attributes: scatterAttributes
      },
      getRadius: this.pointSize,
      getLineColor: this.pointOutlineColor,
      getLineWidth: this.pointLineWidth,
      highlightColor: this.pointHoverColor,
      lineWidthMaxPixels: this.pointLineWidthMaxPixels,
      lineWidthMinPixels: this.pointLineWidthMinPixels,
      radiusMaxPixels: this.pointRadiusMaxPixels,
      radiusMinPixels: this.pointRadiusMinPixels,
      radiusUnits: "common",
      lineWidthUnits: "common",
      autoHighlight: true,
      pickable: true,
      stroked: true,
      extensions: [new deck.DataFilterExtension({ filterSize: 1 })],
      filterRange: [-0.5, 1.5],
      filterSoftRange: [0.75, 1.25],
      updateTriggers: {
        getFilterValue: this.updateTriggerCounter  // We'll increment this to trigger updates
      },
      instanceCount: numPoints,
      parameters: {
        depthTest: false
      }
    });

    this.layers.push(this.pointLayer);
    this.layers.sort((a, b) => getLayerIndex(a) - getLayerIndex(b));
    this._updateLayers();
  }

  /**
   * Add a HexagonLayer for density heatmap visualization.
   *
   * The layer aggregates point positions into hexagonal bins and colors them
   * by count. Re-aggregation only occurs when the zoom crosses one of a fixed
   * number of threshold levels (not on every zoom event) for performance.
   *
   * @param {Object} pointData - The point data object (must have .x and .y arrays)
   * @param {Object} options
   * @param {number}   options.numZoomLevels   - Number of discrete zoom buckets (default 4)
   * @param {number}   options.minCount        - Minimum points in a hex before it is drawn (default 5)
   * @param {Array}    options.colorRange      - Array of [R,G,B] or [R,G,B,A] arrays for the color scale
   * @param {number}   options.baseRadius      - Hex radius in meters at the finest zoom bucket
   * @param {number}   options.coverage        - Hex coverage 0-1 (default 0.8)
   * @param {number}   options.opacity         - Layer opacity 0-1 (default 0.6)
   * @param {Array|null} options.zoomThresholds - Explicit zoom breakpoints (auto-computed if null)
   */
  addHexagonLayer(pointData, {
    numZoomLevels = 4,
    minCount = 5,
    colorRange = [[255, 255, 255, 0], [239, 243, 255], [189, 215, 231], [107, 174, 214], [49, 130, 189], [8, 81, 156]],
    baseRadius = 1000,
    coverage = 1.0,
    opacity = 0.6,
    zoomThresholds = null,
  }) {
    const numPoints = pointData.x.length;

    // Use a lightweight index range as data and read positions from the
    // existing typed arrays via getPosition, avoiding a full copy of all
    // point coordinates into N new [x,y] tuple arrays.
    const indexRange = { length: numPoints };
    this._hexPointData = indexRange;
    this._hexPositionX = pointData.x;
    this._hexPositionY = pointData.y;

    // Compute zoom thresholds
    const initialZoom = this.deckgl.props.initialViewState.zoom;
    if (zoomThresholds && zoomThresholds.length > 0) {
      this._hexZoomThresholds = zoomThresholds.slice().sort((a, b) => a - b);
    } else {
      // Auto-distribute thresholds across a reasonable zoom range
      const zoomMin = Math.max(initialZoom - 1, 0);
      const zoomMax = initialZoom + 4;
      const step = (zoomMax - zoomMin) / numZoomLevels;
      this._hexZoomThresholds = [];
      for (let i = 1; i <= numZoomLevels; i++) {
        this._hexZoomThresholds.push(zoomMin + step * i);
      }
    }

    // Compute radius for each zoom bucket.
    // baseRadius is the coarsest (top-level / most zoomed-out) hex size.
    // Each zoom level subdivides by a fixed factor ofsqrt(2), so more zoom
    // levels produce ever-finer hexagons at the bottom without changing
    // the top-level granularity.
    const HEX_STEP_FACTOR = Math.SQRT2; // sqrt(2) gives a nice visual progression of hex sizes across zoom levels
    const nBuckets = this._hexZoomThresholds.length + 1;
    this._hexRadii = new Array(nBuckets);
    for (let i = 0; i < nBuckets; i++) {
      // Bucket 0 = coarsest (baseRadius), each step down divides by HEX_STEP_FACTOR
      this._hexRadii[i] = baseRadius / Math.pow(HEX_STEP_FACTOR, i);
    }

    // Determine which zoom bucket we start in
    this._currentHexZoomBucket = this._getHexZoomBucket(initialZoom);
    const startRadius = this._hexRadii[this._currentHexZoomBucket];

    // Store hex config for later use
    this._hexMinCount = minCount;
    this._hexColorRange = colorRange;
    this._hexCoverage = coverage;
    this._hexBaseRadius = baseRadius;

    // Build the HexagonLayer
    // When minCount > 0 we need CPU aggregation with getColorValue to filter
    // sparse bins. We prepend a transparent entry to colorRange so bins with
    // value 0 are invisible.
    let hexLayerProps = {
      id: 'hexagonLayer',
      data: this._hexPointData,
      getPosition: (_, { index }) => [this._hexPositionX[index], this._hexPositionY[index]],
      radius: startRadius,
      coverage: coverage,
      opacity: opacity,
      extruded: false,
      colorScaleType: 'quantile',
      pickable: false,
    };

    if (minCount > 0) {
      // CPU aggregation path: return undefined for bins below threshold so
      // they are excluded from rendering entirely
      hexLayerProps.colorRange = colorRange;
      hexLayerProps.getColorValue = (points) => {
        return points.length >= minCount ? points.length : undefined;
      };
      hexLayerProps.gpuAggregation = false;
    } else {
      hexLayerProps.colorRange = colorRange;
      hexLayerProps.getColorWeight = 1;
      hexLayerProps.colorAggregation = 'COUNT';
      hexLayerProps.gpuAggregation = true;
    }

    this.hexagonLayer = new deck.HexagonLayer(hexLayerProps);

    // Store full props for recreation on zoom transitions (ensures
    // color domain is recomputed from scratch at each zoom level)
    this._hexLayerProps = hexLayerProps;

    this.layers.push(this.hexagonLayer);
    this.layers.sort((a, b) => getLayerIndex(a) - getLayerIndex(b));
    this._updateLayers();

    // Set up zoom-bucketed re-aggregation listener
    this._setupHexZoomListener();
  }

  /**
   * Determine which zoom bucket a given zoom level falls into.
   * Bucket 0 = below first threshold (most zoomed out),
   * Bucket N = above last threshold (most zoomed in).
   */
  _getHexZoomBucket(zoom) {
    for (let i = 0; i < this._hexZoomThresholds.length; i++) {
      if (zoom < this._hexZoomThresholds[i]) return i;
    }
    return this._hexZoomThresholds.length;
  }

  /**
   * Register a view-state-change listener that re-aggregates the hex layer
   * only when the zoom crosses a bucket boundary.
   */
  _setupHexZoomListener() {
    let debounceTimer = null;
    const DEBOUNCE_MS = 150;

    this.onViewStateChange('hexZoom', (params) => {
      if (debounceTimer) clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        const zoom = params.viewState.zoom;
        const newBucket = this._getHexZoomBucket(zoom);
        if (newBucket !== this._currentHexZoomBucket) {
          this._currentHexZoomBucket = newBucket;
          this._updateHexRadius(this._hexRadii[newBucket]);
        }
      }, DEBOUNCE_MS);
    });
  }

  /**
   * Recreate the hexagon layer with a new radius, forcing full
   * re-aggregation and color domain recomputation so the color scale
   * adapts to the count range at each zoom level.
   */
  _updateHexRadius(newRadius) {
    if (!this.hexagonLayer) return;

    const idx = this.layers.indexOf(this.hexagonLayer);
    if (idx === -1) return;

    // Build a brand-new layer so deck.gl recomputes aggregation
    // and color domain from scratch (clone may reuse cached state).
    const updatedLayer = new deck.HexagonLayer({
      ...this._hexLayerProps,
      radius: newRadius,
    });
    this.layers = [...this.layers.slice(0, idx), updatedLayer, ...this.layers.slice(idx + 1)];
    this._updateLayers();
    this.hexagonLayer = updatedLayer;
  }

  addEdges(edgeData, {
    edgeWidth = 0.05,
    edgeOpacity = 0.8,
  }) {
    const numEdges = edgeData.r.length;
    this.edgeWidth = edgeWidth;
    this.edgeOpacity = edgeOpacity;

    const sourcePosition = new Float32Array(numEdges * 2);
    const targetPosition = new Float32Array(numEdges * 2);
    const colors = new Uint8Array(numEdges * 4);

    let lineAttributes = {
      getSourcePosition: { value: sourcePosition, size: 2 },
      getTargetPosition: { value: targetPosition, size: 2 },
      getColor: { value: colors, size: 4 },
    };

    // Populate the arrays
    for (let i = 0; i < numEdges; i++) {
      sourcePosition[i * 2] = edgeData.x1[i];
      sourcePosition[i * 2 + 1] = edgeData.y1[i];
      targetPosition[i * 2] = edgeData.x2[i];
      targetPosition[i * 2 + 1] = edgeData.y2[i];
      colors[i * 4] = edgeData.r[i];
      colors[i * 4 + 1] = edgeData.g[i];
      colors[i * 4 + 2] = edgeData.b[i];
      colors[i * 4 + 3] = 180;
    }

    this.edgeLayer = new deck.LineLayer({
      id: 'edgeLayer',
      data: {
        length: numEdges,
        attributes: lineAttributes
      },
      getSourcePosition: d => [d.source.x, d.source.y],
      getTargetPosition: d => [d.target.x, d.target.y],
      getWidth: this.edgeWidth,
    });

    this.layers.push(this.edgeLayer);
    this.layers.sort((a, b) => getLayerIndex(a) - getLayerIndex(b));
    this._updateLayers();
  }

  addLabels(labelData, {
    labelTextColor = d => [d.r, d.g, d.b],
    textMinPixelSize = 18,
    textMaxPixelSize = 36,
    textOutlineWidth = 8,
    textOutlineColor = [238, 238, 238, 221],
    textBackgroundColor = [255, 255, 255, 64],
    fontFamily = "Roboto",
    fontWeight = 900,
    lineSpacing = 0.95,
    textCollisionSizeScale = 3.0,
    noiseLabel = "Unlabelled",
    pickable = false,
  }) {

    const numLabels = labelData.length;
    this.labelTextColor = labelTextColor;
    this.textMinPixelSize = textMinPixelSize;
    this.textMaxPixelSize = textMaxPixelSize;
    this.textOutlineWidth = textOutlineWidth;
    this.textOutlineColor = textOutlineColor;
    this.textBackgroundColor = textBackgroundColor;
    this.fontFamily = fontFamily;
    this.fontWeight = fontWeight;
    this.lineSpacing = lineSpacing;
    this.textCollisionSizeScale = textCollisionSizeScale;

    waitForFont(this.fontFamily);

    this.labelLayer = new deck.TextLayer({
      id: 'labelLayer',
      // Only add labels with valid x positions.
      data: labelData.filter(d => d.label !== noiseLabel),
      pickable: pickable,
      getPosition: d => [d.x, d.y],
      getText: d => d.label,
      getColor: this.labelTextColor,
      getSize: d => d.size,
      sizeScale: 1,
      sizeMinPixels: this.textMinPixelSize,
      sizeMaxPixels: this.textMaxPixelSize,
      outlineWidth: this.textOutlineWidth,
      outlineColor: this.textOutlineColor,
      getBackgroundColor: this.textBackgroundColor,
      getBackgroundPadding: [15, 15, 15, 15],
      background: true,
      characterSet: "auto",
      fontFamily: this.fontFamily,
      fontWeight: this.fontWeight,
      lineHeight: this.lineSpacing,
      fontSettings: { "sdf": true },
      getTextAnchor: "middle",
      getAlignmentBaseline: "center",
      lineHeight: 0.95,
      elevation: 100,
      // CollideExtension options
      collisionEnabled: true,
      getCollisionPriority: d => d.collision_priority ?? d.size,
      collisionTestProps: {
        sizeScale: this.textCollisionSizeScale,
        sizeMaxPixels: this.textMaxPixelSize * 2,
        sizeMinPixels: this.textMinPixelSize * 2
      },
      extensions: [new deck.CollisionFilterExtension()],
      instanceCount: numLabels,
      parameters: {
        depthTest: false
      }
    });

    this.layers.push(this.labelLayer);
    this.layers.sort((a, b) => getLayerIndex(a) - getLayerIndex(b));
    this._updateLayers();
  }

  addBoundaries(boundaryData, { clusterBoundaryLineWidth = 0.5 }) {
    const numBoundaries = boundaryData.length;
    this.clusterBoundaryLineWidth = clusterBoundaryLineWidth;

    this.boundaryLayer = new deck.PolygonLayer({
      id: 'boundaryLayer',
      data: boundaryData,
      stroked: true,
      filled: false,
      getLineColor: d => [d.r, d.g, d.b, d.a],
      getPolygon: d => d.polygon,
      lineWidthUnits: "common",
      getLineWidth: d => d.size * d.size,
      lineWidthScale: this.clusterBoundaryLineWidth * 5e-5,
      lineJointRounded: true,
      lineWidthMaxPixels: 4,
      lineWidthMinPixels: 0.0,
      instanceCount: numBoundaries,
      parameters: {
        depthTest: false
      }
    });

    this.layers.push(this.boundaryLayer);
    this.layers.sort((a, b) => getLayerIndex(a) - getLayerIndex(b));
    this._updateLayers();
  }

  addMetaData(metaData, {
    tooltipFunction = ({ index }) => this.metaData.hover_text[index],
    onClickFunction = null,
    searchField = null,

  }) {
    this.metaData = metaData;
    this.tooltipFunction = tooltipFunction;
    this.onClickFunction = onClickFunction;
    this.searchField = searchField;

    // If hover_text is present, add a tooltip. With tap-to-inspect active
    // the hover tooltip stays mouse/pen-only; touch taps show the same
    // content in the tap-to-inspect card instead.
    if (this.metaData.hasOwnProperty('hover_text')) {
      const getTooltip = this._tapInspect
        ? this._tapInspect.wrapTooltip(this.tooltipFunction)
        : this.tooltipFunction;
      this.deckgl.setProps({
        getTooltip: (info) => getTooltip(this.pickRemap ? this.pickRemap(info) : info),
      });
    }

    if (this.onClickFunction) {
      this.onClick('metaDataOnClick', (info, event) => {
        // With tap-to-inspect active, touch taps open the card and expose
        // on_click as its action button rather than firing it directly.
        if (this._tapInspect && this._tapInspect.shouldSuppressUserClick(info, event)) {
          return;
        }
        this.onClickFunction(info, event);
      });
    }

    //  if search is enabled, add search data array
    if (this.searchField) {
      this.searchArray = this.metaData[this.searchField].map(d => d.toLowerCase());
    }
  }

  connectHistogram(histogramItem) {
    this.histogramItem = histogramItem;
    this.histogramItemId = histogramItem.state.chart.chartContainerId;
  }

  addBackgroundImage(image, bounds) {
    this.imageLayer = new deck.BitmapLayer({
      id: 'imageLayer',
      bounds: bounds,
      image: image,
      parameters: {
        depthTest: false
      }
    });

    this.layers.push(this.imageLayer);
    this.layers.sort((a, b) => getLayerIndex(a) - getLayerIndex(b));
    this._updateLayers();
  }

  addDensityOverview(tilePyramids, fullBounds, crossfadeRange, pointSize, dataXRange, dataYRange, tileResolution, targetRadiusMin, targetLineWidthMin) {
    // tilePyramids: { field: [ [level0_tiles], [level1_tiles], ... ] }
    //   each tile: { row, col, bounds: [left,bottom,right,top], image: uri }
    this._densityTilePyramids = tilePyramids;
    this._densityFullBounds = fullBounds;
    this._densityTileResolution = tileResolution;
    this._densityOverviewTargetRadiusMin = targetRadiusMin;
    this._densityOverviewTargetLineWidthMin = targetLineWidthMin;
    this._densityOverviewLastT = null;
    this._densityOverviewSuppressed = false;
    this._densityCurrentField = "none";

    const currentZoom = this.deckgl.viewManager
      ? this.deckgl.viewManager.getViewState().zoom
      : this.deckgl.props.initialViewState.zoom;

    // Auto-compute crossfade range
    if (crossfadeRange == null) {
      const vw = this.deckgl.canvas ? this.deckgl.canvas.clientWidth : 1500;
      const pixelsPerUnit = vw / dataXRange;
      const pixelRadiusAtZ0 = pointSize * pixelsPerUnit;
      const targetPixelRadius = 1.0;
      const zoomToVisible = Math.log2(targetPixelRadius / Math.max(pixelRadiusAtZ0, 1e-12));
      // Extend the crossfade well beyond the point-visible threshold so
      // the density-to-points transition feels gradual rather than abrupt.
      crossfadeRange = Math.max(3.0, zoomToVisible * 1.5);
    }

    const crossfadeStart = currentZoom;
    const crossfadeEnd = currentZoom + crossfadeRange;
    this._densityOverviewConfig = { crossfadeStart, crossfadeEnd };

    // Compute zoom thresholds for tile-level transitions.
    // Each level doubles effective resolution, so each spans ~1 zoom level.
    const pyramid = tilePyramids["none"] || [];
    const nLevels = pyramid.length;
    this._densityZoomThresholds = [];
    if (nLevels > 1) {
      const levelStep = crossfadeRange / nLevels;
      for (let i = 1; i < nLevels; i++) {
        this._densityZoomThresholds.push(currentZoom + levelStep * i);
      }
    }
    // Width (in zoom levels) of the cross-dissolve zone centred on each
    // level threshold.  40% of a level-step keeps the blend smooth without
    // requiring both levels visible for the full step.
    this._densityLevelBlendWidth = nLevels > 1
      ? Math.min(1.0, (crossfadeRange / nLevels) * 0.4)
      : 0;
    this._densityCurrentLevel = 0;
    this._densityBlendLevel = null;  // secondary level during cross-dissolve

    // Create BitmapLayers for level 0
    this._densityTileLayers = [];
    this._setDensityTileLevel(0, 1.0);

    this.onViewStateChange('densityOverviewCrossfade', (params) => {
      this._updateDensityCrossfade(params.viewState);
    });
  }

  _getDensityZoomLevel(zoom) {
    for (let i = 0; i < this._densityZoomThresholds.length; i++) {
      if (zoom < this._densityZoomThresholds[i]) return i;
    }
    return this._densityZoomThresholds.length;
  }

  _setDensityTileLevel(level, opacity) {
    // Remove old density tile layers from the main layer list
    this.layers = this.layers.filter(l => !l.id.startsWith('densityOverviewLayer_'));
    this._densityTileLayers = [];
    this._densityBlendLevel = null;

    const pyramid = this._densityTilePyramids[this._densityCurrentField]
      || this._densityTilePyramids["none"] || [];
    const tiles = pyramid[level] || [];

    for (const tile of tiles) {
      const layer = new deck.BitmapLayer({
        id: `densityOverviewLayer_L${level}_R${tile.row}_C${tile.col}`,
        bounds: tile.bounds,
        image: tile.image,
        opacity: opacity,
        parameters: { depthTest: false },
      });
      this._densityTileLayers.push(layer);
      this.layers.push(layer);
    }

    this._densityCurrentLevel = level;
    this.layers.sort((a, b) => getLayerIndex(a) - getLayerIndex(b));
    this._updateLayers();
  }

  // Show two adjacent tile levels simultaneously for a smooth cross-dissolve.
  _setDensityDualLevel(levelA, opacityA, levelB, opacityB) {
    this.layers = this.layers.filter(l => !l.id.startsWith('densityOverviewLayer_'));
    this._densityTileLayers = [];

    const pyramid = this._densityTilePyramids[this._densityCurrentField]
      || this._densityTilePyramids["none"] || [];

    for (const [level, opacity] of [[levelA, opacityA], [levelB, opacityB]]) {
      const tiles = pyramid[level] || [];
      for (const tile of tiles) {
        const layer = new deck.BitmapLayer({
          id: `densityOverviewLayer_L${level}_R${tile.row}_C${tile.col}`,
          bounds: tile.bounds,
          image: tile.image,
          opacity: opacity,
          parameters: { depthTest: false },
        });
        this._densityTileLayers.push(layer);
        this.layers.push(layer);
      }
    }

    this._densityCurrentLevel = levelA;
    this._densityBlendLevel = levelB;
    this.layers.sort((a, b) => getLayerIndex(a) - getLayerIndex(b));
    this._updateLayers();
  }

  _updateDensityCrossfade(viewState) {
    if (!this._densityOverviewConfig) return;

    // While a selection (e.g. search results) is active the overview is
    // suppressed so that the selected points remain visible; skip crossfade
    // updates entirely until the selection is cleared.
    if (this._densityOverviewSuppressed) return;

    const { crossfadeStart, crossfadeEnd } = this._densityOverviewConfig;
    const zoom = viewState.zoom;
    const rawT = Math.max(0, Math.min(1, (zoom - crossfadeStart) / (crossfadeEnd - crossfadeStart)));
    // Apply easing (cubic in-out)
    const t = rawT < 0.5
      ? 4 * rawT * rawT * rawT
      : 1 - Math.pow(-2 * rawT + 2, 3) / 2;

    // Skip update if t hasn't changed meaningfully
    const quantized = Math.round(t * 200);
    if (quantized === this._densityOverviewLastT) return;
    this._densityOverviewLastT = quantized;

    const overallOpacity = 1 - t;
    const targetLevel = this._getDensityZoomLevel(zoom);
    const halfBlend = this._densityLevelBlendWidth / 2;

    // Determine whether we are inside a cross-dissolve zone around a
    // level threshold.  If so, blend between the two adjacent levels.
    let needDual = false;
    let levelA = targetLevel;
    let levelB = -1;
    let blendT = 0; // 0 = fully levelA, 1 = fully levelB

    if (halfBlend > 0) {
      // Check threshold we just crossed into targetLevel
      if (targetLevel > 0) {
        const th = this._densityZoomThresholds[targetLevel - 1];
        const d = zoom - th;
        if (d >= 0 && d < halfBlend) {
          levelA = targetLevel - 1;
          levelB = targetLevel;
          blendT = 0.5 + (d / this._densityLevelBlendWidth);
          needDual = true;
        }
      }
      // Check threshold we are approaching from targetLevel
      if (!needDual && targetLevel < this._densityZoomThresholds.length) {
        const th = this._densityZoomThresholds[targetLevel];
        const d = th - zoom;
        if (d >= 0 && d < halfBlend) {
          levelA = targetLevel;
          levelB = targetLevel + 1;
          blendT = 0.5 - (d / this._densityLevelBlendWidth);
          needDual = true;
        }
      }
    }

    if (needDual) {
      const opA = overallOpacity * (1 - blendT);
      const opB = overallOpacity * blendT;
      this._setDensityDualLevel(levelA, opA, levelB, opB);
    } else if (targetLevel !== this._densityCurrentLevel || this._densityBlendLevel !== null) {
      // Exited a blend zone or changed level — snap to single level
      this._setDensityTileLevel(targetLevel, overallOpacity);
    } else {
      // Same level, just update opacity on existing tile layers
      for (let i = 0; i < this._densityTileLayers.length; i++) {
        const oldLayer = this._densityTileLayers[i];
        const idx = this.layers.indexOf(oldLayer);
        if (idx !== -1) {
          const updated = oldLayer.clone({ opacity: overallOpacity });
          this.layers[idx] = updated;
          this._densityTileLayers[i] = updated;
        }
      }
    }

    // Update point layer opacity, radiusMinPixels, lineWidthMinPixels
    const origRadius = this._densityOverviewTargetRadiusMin;
    const origLineWidth = this._densityOverviewTargetLineWidthMin;
    const pointIdx = this.layers.indexOf(this.pointLayer);
    if (pointIdx !== -1) {
      const updatedPoints = this.pointLayer.clone({
        opacity: t,
        radiusMinPixels: t * origRadius,
        lineWidthMinPixels: t * origLineWidth,
      });
      this.layers[pointIdx] = updatedPoints;
      this.pointLayer = updatedPoints;
    }

    this._updateLayers();
  }

  _swapDensityOverviewImage(field) {
    if (!this._densityTilePyramids) return;
    this._densityCurrentField = field;
    // Determine current opacity from one of the active tiles
    const curOpacity = this._densityTileLayers.length > 0
      ? (this._densityTileLayers[0].props.opacity !== undefined
        ? this._densityTileLayers[0].props.opacity : 1.0)
      : 1.0;
    this._setDensityTileLevel(this._densityCurrentLevel, curOpacity);
  }

  async addSelectionHandler(callback, selectionKind = "lasso-selection", timeoutMs = 60000) {
    const startTime = Date.now();

    if (selectionKind === "lasso-selection") {
      // Wait for the lasso selector to be available
      while (!this.lassoSelector) {
        if (Date.now() - startTime > timeoutMs) {
          throw new Error('Timeout: lassoSelector did not become available within the specified timeout period');
        }
        await new Promise(resolve => setTimeout(resolve, 1000));
      }

      this.lassoSelector.registerSelectionHandler(callback);
    } else {
      if (!this.selectionCallbacks) {
        this.selectionCallbacks = {};
      }
      if (this.selectionCallbacks[selectionKind]) {
        this.selectionCallbacks[selectionKind].push(callback);
      }
      this.selectionCallbacks[selectionKind] = [callback];
    }
  }

  highlightPoints(itemId) {
    const selectedIndices = this.dataSelectionManager.getSelectedIndices();
    const semiSelectedIndices = this.dataSelectionManager.getBasicSelectedIndices();
    const hasSelectedIndices = selectedIndices.size !== 0;
    const hasSemiSelectedIndices = semiSelectedIndices.size !== 0;
    const hasLassoSelection = this.dataSelectionManager.hasSpecialSelection();

    // Update selected array
    if (hasLassoSelection) {
      if (hasSelectedIndices) {
        if (hasSemiSelectedIndices) {
          this.selected.fill(-1.0);
          for (let i of semiSelectedIndices) {
            this.selected[i] = 0.0;
          }
        } else {
          this.selected.fill(0.0);
        }
        for (let i of selectedIndices) {
          this.selected[i] = 1.0;
        }
      } else {
        this.selected.fill(1.0);
      }
    } else {
      if (hasSelectedIndices) {
        this.selected.fill(-1.0);
        for (let i of selectedIndices) {
          this.selected[i] = 1.0;
        }
      } else {
        this.selected.fill(1.0);
      }
    }
    // Increment update trigger
    this.updateTriggerCounter++;

    const sizeAdjust = 1 / (1 + (Math.sqrt(selectedIndices.size) / Math.log2(this.selected.length)));

    // When a density overview is active and there is an active selection
    // (e.g. search results) we must suppress the overview, which would
    // otherwise occlude the selected points when zoomed out, and force the
    // points to be fully visible regardless of the crossfade zoom state.
    const overviewActive = !!this._densityOverviewConfig;
    const suppressOverview = overviewActive && hasSelectedIndices;
    const overviewSuppressionChanged =
      overviewActive && this._densityOverviewSuppressed !== suppressOverview;
    if (overviewActive) {
      this._densityOverviewSuppressed = suppressOverview;
    }

    const pointOpacityOverride = suppressOverview
      ? 1.0
      : this.pointLayer.props.opacity;

    const updatedPointLayer = this.pointLayer.clone({
      data: {
        ...this.pointLayer.props.data,
        attributes: {
          ...this.pointLayer.props.data.attributes,
          getFilterValue: { value: this.selected, size: 1 }
        }
      },
      opacity: pointOpacityOverride,
      radiusMinPixels: hasSelectedIndices ? 2 * (this.pointRadiusMinPixels + sizeAdjust) : this.pointRadiusMinPixels,
      updateTriggers: {
        getFilterValue: this.updateTriggerCounter,
        radiusMinPixels: this.updateTriggerCounter,
      }
    });

    const idx = this.layers.indexOf(this.pointLayer);
    this.layers = [...this.layers.slice(0, idx), updatedPointLayer, ...this.layers.slice(idx + 1)];
    this.pointLayer = updatedPointLayer;

    // Hide or restore the density overview tile layers depending on whether
    // there is now an active selection to display.
    if (suppressOverview) {
      for (let i = 0; i < this._densityTileLayers.length; i++) {
        const oldLayer = this._densityTileLayers[i];
        const layerIdx = this.layers.indexOf(oldLayer);
        if (layerIdx !== -1) {
          const updated = oldLayer.clone({ opacity: 0 });
          this.layers[layerIdx] = updated;
          this._densityTileLayers[i] = updated;
        }
      }
    }

    this._updateLayers();

    // When the selection has just been cleared, restore the overview to the
    // appropriate crossfade state for the current zoom level.
    if (overviewActive && overviewSuppressionChanged && !suppressOverview) {
      this._densityOverviewLastT = null;
      const viewState = this.deckgl.viewManager
        ? this.deckgl.viewManager.getViewState()
        : this.deckgl.props.initialViewState;
      this._updateDensityCrossfade(viewState);
    }

    // Update label visibility when search filter is active
    if (this.labelLayer) {
      const filteringSearch = itemId === this.searchItemId && this.filterLabelsOnSearch && hasSelectedIndices;
      if (!this._allLabelData) {
        this._allLabelData = this.labelLayer.props.data;
      }
      const filteredData = filteringSearch
        ? this._allLabelData.filter(d => d.relatedPoints && d.relatedPoints.some(i => selectedIndices.has(i)))
        : this._allLabelData;
      const updatedLabelLayer = this.labelLayer.clone({
        data: filteredData,
        updateTriggers: { data: this.updateTriggerCounter },
      });
      const labelIdx = this.layers.indexOf(this.labelLayer);
      if (labelIdx !== -1) {
        this.layers = [...this.layers.slice(0, labelIdx), updatedLabelLayer, ...this.layers.slice(labelIdx + 1)];
        this._updateLayers();
        this.labelLayer = updatedLabelLayer;
      }
    }

    // Update histogram, if any
    if (this.histogramItem && itemId !== this.histogramItemId) {
      if (hasSelectedIndices) {
        this.histogramItem.drawChartWithSelection(selectedIndices);
      } else {
        this.histogramItem.removeChartWithSelection(selectedIndices);
      }
    }
    this._emit(this._selectionListeners, 'selectionChange');
  }

  addSelection(selectedIndices, selectionKind) {
    this.dataSelectionManager.addOrUpdateSelectedIndicesOfItem(selectedIndices, selectionKind);
    this.highlightPoints(selectionKind);

    if (this.selectionCallbacks && this.selectionCallbacks[selectionKind]) {
      const currentSelectedIndices = Array.from(this.dataSelectionManager.getSelectedIndices());
      for (let callback of this.selectionCallbacks[selectionKind]) {
        callback(currentSelectedIndices);
      }
    }
  }

  removeSelection(selectionKind) {
    this.dataSelectionManager.removeSelectedIndicesOfItem(selectionKind);
    this.highlightPoints(selectionKind);

    if (this.selectionCallbacks && this.selectionCallbacks[selectionKind]) {
      const currentSelectedIndices = Array.from(this.dataSelectionManager.getSelectedIndices());
      for (let callback of this.selectionCallbacks[selectionKind]) {
        callback(currentSelectedIndices);
      }
    }
  }

  getSelectedIndices() {
    return this.dataSelectionManager.getSelectedIndices();
  }

  refreshSelection() {
    this.highlightPoints();
  }

  searchText(searchTerm) {
    const searchTermLower = searchTerm.toLowerCase();
    const selectedIndices = this.searchArray.reduce((indices, d, i) => {
      if (d.indexOf(searchTermLower) >= 0) {
        indices.push(i);
      }
      return indices;
    }, []);
    if (searchTerm === "") {
      this.dataSelectionManager.removeSelectedIndicesOfItem(this.searchItemId);
    } else {
      this.dataSelectionManager.addOrUpdateSelectedIndicesOfItem(selectedIndices, this.searchItemId);
    }
    if (this.selectionCallbacks && this.selectionCallbacks[this.searchItemId]) {
      const currentSelectedIndices = Array.from(this.dataSelectionManager.getSelectedIndices());
      for (let callback of this.selectionCallbacks[this.searchItemId]) {
        callback(currentSelectedIndices);
      }
    }
    this.highlightPoints(this.searchItemId);
  }

  recolorPoints(colorData, fieldName) {
    if (!this.hasOwnProperty(`${fieldName}Colors`)) {
      const numPoints = colorData[`${fieldName}_r`].length;
      const colors = new Uint8Array(numPoints * 4);
      for (let i = 0; i < numPoints; i++) {
        colors[i * 4] = colorData[`${fieldName}_r`][i];
        colors[i * 4 + 1] = colorData[`${fieldName}_g`][i];
        colors[i * 4 + 2] = colorData[`${fieldName}_b`][i];
        colors[i * 4 + 3] = colorData[`${fieldName}_a`][i];
      }
      this[`${fieldName}Colors`] = colors;
    }

    const updatedPointLayer = this.pointLayer.clone({
      data: {
        ...this.pointLayer.props.data,
        attributes: {
          ...this.pointLayer.props.data.attributes,
          getFillColor: { value: this[`${fieldName}Colors`], size: 4 }
        }
      },
      transitions: {
        getFillColor: {
          duration: 1500,
          easing: d3.easeCubicInOut
        }
      }
    });

    // Increment update trigger
    this.updateTriggerCounter++;

    const idx = this.layers.indexOf(this.pointLayer);
    this.layers = [...this.layers.slice(0, idx), updatedPointLayer, ...this.layers.slice(idx + 1)];
    this._updateLayers();
    this.pointLayer = updatedPointLayer;
    this._swapDensityOverviewImage(fieldName);
    this._emit(this._pointColorsListeners, 'pointColorsChange');
  }

  resetPointColors() {
    const updatedPointLayer = this.pointLayer.clone({
      data: {
        ...this.pointLayer.props.data,
        attributes: {
          ...this.pointLayer.props.data.attributes,
          getFillColor: { value: this.originalColors, size: 4 }
        }
      },
      transitions: {
        getFillColor: {
          duration: 1500,
          easing: d3.easeCubicInOut
        }
      }
    });

    // Increment update trigger
    this.updateTriggerCounter++;

    const idx = this.layers.indexOf(this.pointLayer);
    this.layers = [...this.layers.slice(0, idx), updatedPointLayer, ...this.layers.slice(idx + 1)];
    this._updateLayers();
    this.pointLayer = updatedPointLayer;
    this._swapDensityOverviewImage("none");
    this._emit(this._pointColorsListeners, 'pointColorsChange');
  }

  // ------------------------------------------------------------------
  // API for widgets that draw their own view of the data on the map (e.g. the
  // re-embed widget). They should use these methods rather than DataMap's
  // fields and deck.gl props, which may change between versions.

  /** The layers deck.gl draws: the map's own, with overlay layers where the point layer is. */
  _composeLayers() {
    const others = this._baseDisplay.others;
    const isPoints = (layer) => layer.id === 'dataPointLayer';
    const layers = others > 0 && others < 1
      ? this.layers.map((layer) => (isPoints(layer) ? layer : layer.clone({ opacity: (layer.props.opacity ?? 1) * others })))
      : [...this.layers];
    if (this._overlayIds.length) {
      let at = layers.findIndex(isPoints);
      if (at < 0) at = layers.length;
      layers.splice(at, 0, ...[...this._overlayLayers.values()].flat());
    }
    return layers;
  }

  _updateLayers() {
    this.deckgl.setProps({ layers: this._composeLayers() });
  }

  /**
   * Draw a widget's own deck.gl layers on the map, where the point layer is (above
   * the background and density overview, below the points and everything above them).
   * They are kept through the map's own layer updates.
   * @param {string} ownerId  Key for the widget's layers.
   * @param {Array} layers  deck.gl layers, replacing the owner's previous ones
   *   (empty to remove them). Ids must be unique on the map.
   */
  setOverlayLayers(ownerId, layers) {
    if (layers && layers.length) this._overlayLayers.set(ownerId, layers);
    else this._overlayLayers.delete(ownerId);
    this._overlayIds = [...this._overlayLayers.values()].flat().map((layer) => layer.id);
    this._updateLayers();
  }

  /**
   * Show, dim or hide the map's own layers, e.g. while a widget shows its own
   * view of the data in overlay layers (which are not affected).
   * @param {Object} [display]
   * @param {boolean} [display.points=true]  Whether the point layer is drawn.
   * @param {number} [display.others=1]  Opacity factor (0 to 1) for all the map's
   *   other layers, on top of their own opacity; 0 hides them.
   */
  setBaseLayerDisplay({ points = true, others = 1 } = {}) {
    const previous = this._baseDisplay;
    const next = { points: !!points, others: Math.min(1, Math.max(0, others)) };
    this._baseDisplay = next;
    if (previous.points !== next.points || (previous.others === 0) !== (next.others === 0)) {
      // Hidden layers stay in deck.gl (keeping their GPU state) and are filtered out.
      const showOthers = next.others > 0;
      const isOverlay = (id) => this._overlayIds.some((o) => id === o || id.startsWith(o + '-'));
      this.deckgl.setProps({
        layerFilter: next.points && showOthers ? null
          : ({ layer }) => isOverlay(layer.id) || (layer.id.startsWith('dataPointLayer') ? next.points : showOthers),
      });
    }
    this._updateLayers();
  }

  /**
   * The map's points as currently drawn, or null before they are added:
   * `count`; `positions` (x, y interleaved); `colors` (RGBA, of the current
   * colormap); `radii` (per point) or null, with `size` the radius of every point.
   */
  getPoints() {
    if (!this.pointLayer) return null;
    const attributes = this.pointLayer.props.data.attributes;
    return {
      count: this.pointLayer.props.data.length,
      positions: attributes.getPosition.value,
      colors: attributes.getFillColor.value,
      radii: attributes.getRadius ? attributes.getRadius.value : null,
      size: this.pointSize,
    };
  }

  /**
   * Styling of the point layer: as configured, plus `displayedRadiusMinPixels`
   * and `displayedOpacity` as currently drawn (they vary with the density
   * overview crossfade and the selection).
   */
  getPointStyle() {
    const props = this.pointLayer ? this.pointLayer.props : {};
    return {
      outlineColor: this.pointOutlineColor,
      lineWidth: this.pointLineWidth,
      lineWidthMinPixels: this.pointLineWidthMinPixels,
      lineWidthMaxPixels: this.pointLineWidthMaxPixels,
      radiusMinPixels: this.pointRadiusMinPixels,
      radiusMaxPixels: this.pointRadiusMaxPixels,
      hoverColor: this.pointHoverColor,
      displayedRadiusMinPixels: props.radiusMinPixels ?? this.pointRadiusMinPixels,
      displayedOpacity: props.opacity ?? 1,
    };
  }

  /**
   * Each point's selection state (do not modify): 1 selected, or everything
   * when there is no selection; 0 for points of a basic selection outside the
   * lasso; -1 not selected. Updated before selection-change listeners are called.
   */
  getPointSelectionState() {
    return this.selected;
  }

  /** Whether there is a lasso selection. */
  hasLassoSelection() {
    return this.dataSelectionManager.hasSpecialSelection();
  }

  /** Remove the lasso selection, if any. */
  clearLassoSelection() {
    if (this.hasLassoSelection()) this.removeSelection(this.lassoSelectionItemId);
  }

  /**
   * Set which points the lasso selects from, and where they are.
   * @param {Float32Array|null} positions  x, y interleaved, indexed by point
   *   (null keeps the current positions).
   * @param {ArrayLike<number>|null} [indices=null]  The selectable points (all
   *   when null; none when empty).
   */
  setSelectablePoints(positions, indices = null) {
    const lasso = this.lassoSelector;
    if (!lasso || !lasso.rebuildQuadTree) return;
    const points = positions || lasso.points || (this.getPoints() || {}).positions;
    if (points) lasso.rebuildQuadTree(points, indices);
  }

  /** All the map's labels, including any hidden by a search filter. */
  getLabelData() {
    if (this._allLabelData) return this._allLabelData;
    return this.labelLayer ? this.labelLayer.props.data : [];
  }

  /**
   * A new label layer styled like the map's, with `props` overriding (e.g. `id`,
   * `data`, `opacity`), or null if the map has no labels.
   */
  createLabelLayer(props) {
    return this.labelLayer ? this.labelLayer.clone(props) : null;
  }

  /** The current deck.gl viewport, or null before the first render. */
  getViewport() {
    const viewManager = this.deckgl.viewManager;
    return (viewManager && viewManager.getViewports()[0]) || null;
  }

  /** Size of the map in pixels. */
  getViewportSize() {
    const viewport = this.getViewport();
    if (viewport) return { width: viewport.width, height: viewport.height };
    return { width: this.container.clientWidth, height: this.container.clientHeight };
  }

  /** The current camera: { longitude, latitude, zoom }. */
  getViewState() {
    const v = this.getViewport() || this.deckgl.props.initialViewState;
    return { longitude: v.longitude, latitude: v.latitude, zoom: v.zoom };
  }

  /**
   * Move the camera.
   * @param {Object} viewState  { longitude, latitude, zoom }.
   * @param {Object} [options]
   * @param {boolean} [options.notify=true]  Bring view-state listeners and
   *   view-dependent layers to the new view (see notifyViewStateChange).
   */
  setViewState(viewState, { notify = true } = {}) {
    this.deckgl.setProps({ initialViewState: { pitch: 0, bearing: 0, ...viewState } });
    if (notify) this.notifyViewStateChange(viewState, { force: true });
  }

  /**
   * Update deck.gl controller options (e.g. `{ dragPan: false }`), merged with
   * the map's current ones. Use this rather than setting deck.gl's `controller`,
   * so interaction locks are respected.
   */
  setControllerOptions(options) {
    Object.assign(this._controllerOptions, options);
    this._applyController();
  }

  /** Disable user interaction (pan, zoom) until `unlockInteraction(ownerId)`. */
  lockInteraction(ownerId) {
    this._interactionLocks.add(ownerId);
    this._applyController();
  }

  /** Release an interaction lock; interaction resumes when no lock is held. */
  unlockInteraction(ownerId) {
    this._interactionLocks.delete(ownerId);
    this._applyController();
  }

  _applyController() {
    this.deckgl.setProps({ controller: this._interactionLocks.size ? false : { ...this._controllerOptions } });
  }

  // Layer management methods for widgets
  setLayerVisibility(layerId, visible) {
    // Density overview tiles are controlled as a group
    if (layerId === 'densityOverviewLayer' && this._densityTileLayers && this._densityTileLayers.length > 0) {
      for (let i = 0; i < this._densityTileLayers.length; i++) {
        const oldLayer = this._densityTileLayers[i];
        const idx = this.layers.indexOf(oldLayer);
        if (idx !== -1) {
          const updated = oldLayer.clone({ visible });
          this.layers[idx] = updated;
          this._densityTileLayers[i] = updated;
        }
      }
      this._updateLayers();
      return;
    }

    const layerMap = {
      'imageLayer': this.imageLayer,
      'dataPointLayer': this.pointLayer,
      'labelLayer': this.labelLayer,
      'boundaryLayer': this.boundaryLayer,
      'edgeLayer': this.edgeLayer,
      'hexagonLayer': this.hexagonLayer
    };

    const layer = layerMap[layerId];
    if (!layer) return;

    const idx = this.layers.indexOf(layer);
    if (idx === -1) return;

    const updatedLayer = layer.clone({ visible });
    this.layers = [...this.layers.slice(0, idx), updatedLayer, ...this.layers.slice(idx + 1)];
    this._updateLayers();

    // Update stored reference
    if (layerId === 'dataPointLayer') this.pointLayer = updatedLayer;
    else if (layerId === 'labelLayer') this.labelLayer = updatedLayer;
    else if (layerId === 'boundaryLayer') this.boundaryLayer = updatedLayer;
    else if (layerId === 'edgeLayer') this.edgeLayer = updatedLayer;
    else if (layerId === 'imageLayer') this.imageLayer = updatedLayer;
    else if (layerId === 'hexagonLayer') {
      this.hexagonLayer = updatedLayer;
      this._hexLayerProps = { ...this._hexLayerProps, visible }; // Update stored props for future radius-based re-creation
    }
  }

  setLayerOpacity(layerId, opacity) {
    // Density overview tiles are controlled as a group
    if (layerId === 'densityOverviewLayer' && this._densityTileLayers && this._densityTileLayers.length > 0) {
      for (let i = 0; i < this._densityTileLayers.length; i++) {
        const oldLayer = this._densityTileLayers[i];
        const idx = this.layers.indexOf(oldLayer);
        if (idx !== -1) {
          const updated = oldLayer.clone({ opacity });
          this.layers[idx] = updated;
          this._densityTileLayers[i] = updated;
        }
      }
      this._updateLayers();
      return;
    }

    const layerMap = {
      'imageLayer': this.imageLayer,
      'dataPointLayer': this.pointLayer,
      'labelLayer': this.labelLayer,
      'boundaryLayer': this.boundaryLayer,
      'edgeLayer': this.edgeLayer,
      'hexagonLayer': this.hexagonLayer
    };

    const layer = layerMap[layerId];
    if (!layer) return;

    const idx = this.layers.indexOf(layer);
    if (idx === -1) return;

    const updatedLayer = layer.clone({ opacity });
    this.layers = [...this.layers.slice(0, idx), updatedLayer, ...this.layers.slice(idx + 1)];
    this._updateLayers();

    // Update stored reference
    if (layerId === 'dataPointLayer') this.pointLayer = updatedLayer;
    else if (layerId === 'labelLayer') this.labelLayer = updatedLayer;
    else if (layerId === 'boundaryLayer') this.boundaryLayer = updatedLayer;
    else if (layerId === 'edgeLayer') this.edgeLayer = updatedLayer;
    else if (layerId === 'imageLayer') this.imageLayer = updatedLayer;
    else if (layerId === 'hexagonLayer') {
      this.hexagonLayer = updatedLayer;
      this._hexLayerProps = { ...this._hexLayerProps, opacity }; // Update stored props for future radius-based re-creation
    }
  }

  getLayerVisibility(layerId) {
    if (layerId === 'densityOverviewLayer' && this._densityTileLayers && this._densityTileLayers.length > 0) {
      return this._densityTileLayers[0].props.visible !== false;
    }
    const layerMap = {
      'imageLayer': this.imageLayer,
      'dataPointLayer': this.pointLayer,
      'labelLayer': this.labelLayer,
      'boundaryLayer': this.boundaryLayer,
      'edgeLayer': this.edgeLayer,
      'hexagonLayer': this.hexagonLayer
    };

    const layer = layerMap[layerId];
    return layer ? layer.props.visible !== false : true;
  }

  getLayerOpacity(layerId) {
    if (layerId === 'densityOverviewLayer' && this._densityTileLayers && this._densityTileLayers.length > 0) {
      const l = this._densityTileLayers[0];
      return l.props.opacity !== undefined ? l.props.opacity : 1.0;
    }
    const layerMap = {
      'imageLayer': this.imageLayer,
      'dataPointLayer': this.pointLayer,
      'labelLayer': this.labelLayer,
      'boundaryLayer': this.boundaryLayer,
      'edgeLayer': this.edgeLayer,
      'hexagonLayer': this.hexagonLayer
    };

    const layer = layerMap[layerId];
    return layer ? (layer.props.opacity !== undefined ? layer.props.opacity : 1.0) : 1.0;
  }
}