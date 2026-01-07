
LAYER_ORDER = ['imageLayer', 'dataPointLayer', 'boundaryLayer', 'labelLayer'];

function getLayerIndex(object) {
  return LAYER_ORDER.indexOf(object.id);
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
  }) {
    this.container = container;
    this.searchItemId = searchItemId;
    this.lassoSelectionItemId = lassoSelectionItemId;
    this.pointData = null;
    this.labelData = null;
    this.metaData = null;
    this.layers = [];
    const { viewportWidth, viewportHeight } = getInitialViewportSize();
    const { zoomLevel, dataCenter } = calculateZoomLevel(bounds, viewportWidth, viewportHeight);
    this.deckgl = new deck.DeckGL({
      container: container,
      initialViewState: {
        latitude: dataCenter[1],
        longitude: dataCenter[0],
        zoom: zoomLevel
      },
      controller: { scrollZoom: { speed: 0.01, smooth: true } },
    });
    this.updateTriggerCounter = 0;
    this.dataSelectionManager = new DataSelectionManager(lassoSelectionItemId);

    // Widget registry for inter-widget communication
    this.widgetRegistry = new WidgetRegistry();
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
    this.deckgl.setProps({ layers: [...this.layers] });
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
    this.deckgl.setProps({ layers: [...this.layers] });
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
      getCollisionPriority: d => d.size,
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
    this.deckgl.setProps({ layers: [...this.layers] });
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
    this.deckgl.setProps({ layers: [...this.layers] });
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

    // If hover_text is present, add a tooltip
    if (this.metaData.hasOwnProperty('hover_text')) {
      this.deckgl.setProps({
        getTooltip: this.tooltipFunction,
      });
    }

    if (this.onClickFunction) {
      this.deckgl.setProps({
        onClick: this.onClickFunction,
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
    this.deckgl.setProps({ layers: [...this.layers] });
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

    const updatedPointLayer = this.pointLayer.clone({
      data: {
        ...this.pointLayer.props.data,
        attributes: {
          ...this.pointLayer.props.data.attributes,
          getFilterValue: { value: this.selected, size: 1 }
        }
      },
      radiusMinPixels: hasSelectedIndices ? 2 * (this.pointRadiusMinPixels + sizeAdjust) : this.pointRadiusMinPixels,
      updateTriggers: {
        getFilterValue: this.updateTriggerCounter,
        radiusMinPixels: this.updateTriggerCounter,
      }
    });

    const idx = this.layers.indexOf(this.pointLayer);
    this.layers = [...this.layers.slice(0, idx), updatedPointLayer, ...this.layers.slice(idx + 1)];
    this.deckgl.setProps({
      layers: this.layers
    });
    this.pointLayer = updatedPointLayer;

    // Update histogram, if any
    if (this.histogramItem && itemId !== this.histogramItemId) {
      if (hasSelectedIndices) {
        this.histogramItem.drawChartWithSelection(selectedIndices);
      } else {
        this.histogramItem.removeChartWithSelection(selectedIndices);
      }
    }
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
    this.deckgl.setProps({
      layers: this.layers
    });
    this.pointLayer = updatedPointLayer;
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
    this.deckgl.setProps({
      layers: this.layers
    });
    this.pointLayer = updatedPointLayer;
  }
}