
const LAYER_ORDER = ['dataPointLayer', 'boundaryLayer', 'LabelLayer'];

// There is an effective 100 layer limit of label layers or boundary layers...
function getLayerIndex(object) {
  if (object.id.startsWith('LabelLayer')) {
    return LAYER_ORDER.indexOf('LabelLayer') + (parseInt(object.id.split('-')[1] / 100));
  } else if (object.id.startsWith('boundaryLayer')) {
    return LAYER_ORDER.indexOf('boundaryLayer') + (parseInt(object.id.split('-')[1] / 100));
  } else {
    return LAYER_ORDER.indexOf(object.id);
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

function calculateZoomLevel(bounds, viewportWidth, viewportHeight, padding = 0) {
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
  }

  addPoints(pointData, {
    pointSize,
    pointOutlineColor = [255, 255, 255, 128],
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

  addLabels(labelData, {
    labelTextColor = d => [d.r, d.g, d.b],
    textMinPixelSize = 18,
    textMaxPixelSize = 36,
    textOutlineWidth = 2,
    textOutlineColor = [255, 255, 255, 221],
    textBackgroundColor = [255, 255, 255, 64],
    fontFamily = "Roboto",
    fontWeight = 900,
    lineSpacing = 0.95,
    textCollisionSizeScale = 3.0,
  }) {
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

    this.labelLayers = labelData.map((labelLayerData, index) => {
      const numLabels = labelLayerData.length;
      const layerFontWeight = labelLayerData[0].hasOwnProperty('weight') ? labelLayerData[0].weight : this.fontWeight;
      return new deck.TextLayer({
        id: `LabelLayer-${index}`,
        data: labelLayerData,
        pickable: false,
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
        fontWeight: layerFontWeight,
        lineHeight: this.lineSpacing,
        fontSettings: { "sdf": true },
        getTextAnchor: "middle",
        getAlignmentBaseline: "center",
        lineHeight: 0.95,
        elevation: 100 * (index + 1),
        // CollideExtension options
        extensions: [new deck.CollisionFilterExtension()],
        collisionEnabled: true,
        getCollisionPriority: d => d.layer + d.size / 1000,
        collisionTestProps: {
          sizeScale: this.textCollisionSizeScale,
          sizeMaxPixels: this.textMaxPixelSize * 2,
          sizeMinPixels: this.textMinPixelSize * 2
        },
        // collisionGroup: 'labels',
        instanceCount: numLabels,
        parameters: {
          depthTest: false
        }
      })
    });

    this.labelLayers.forEach(layer => this.layers.push(layer));
    this.layers.sort((a, b) => getLayerIndex(a) - getLayerIndex(b));
    this.deckgl.setProps({ layers: [...this.layers] });
  }

  addBoundaries(boundaryData, {clusterBoundaryLineWidth = 0.5}) {
    this.clusterBoundaryLineWidth = clusterBoundaryLineWidth;

    this.boundaryLayers = boundaryData.map((boundaryLayerData, index) => {
      const numBoundaries = boundaryLayerData.length;
      return new deck.PolygonLayer({
        id: `boundaryLayer-${index}`,
        data: boundaryLayerData,
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
    });

    this.boundaryLayers.forEach(layer => this.layers.push(layer));
    this.layers.sort((a, b) => getLayerIndex(a) - getLayerIndex(b));
    this.deckgl.setProps({ layers: [...this.layers] });
  }

  addMetaData(metaData, {
    tooltipFunction = ({index}) => this.metaData.hover_text[index],
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

    const updatedPointLayer = this.pointLayer.clone({
      data: {
        ...this.pointLayer.props.data,
        attributes: {
          ...this.pointLayer.props.data.attributes,
          getFilterValue: { value: this.selected, size: 1 }
        }
      },
      updateTriggers: {
        getFilterValue: this.updateTriggerCounter
      }
    });

    const idx = this.layers.indexOf(this.pointLayer);
    this.deckgl.setProps({
      layers: [...this.layers.slice(0, idx), updatedPointLayer, ...this.layers.slice(idx + 1)]
    });

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
  }

  removeSelection(selectionKind) {
    this.dataSelectionManager.removeSelectedIndicesOfItem(selectionKind);
    this.highlightPoints(selectionKind);
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
    this.highlightPoints(this.searchItemId);
  }
}