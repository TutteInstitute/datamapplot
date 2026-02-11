/**
 * LayerToggle - UI for controlling visibility and opacity of map layers
 */
class LayerToggle {
    constructor(container, datamap, options = {}) {
        this.container = container;
        this.datamap = datamap;

        this.options = {
            layers: options.layers || [
                { id: 'imageLayer', label: 'Background', visible: true, opacity: 1.0 },
                { id: 'edgeLayer', label: 'Edges', visible: true, opacity: 1.0 },
                { id: 'dataPointLayer', label: 'Points', visible: true, opacity: 1.0 },
                { id: 'labelLayer', label: 'Labels', visible: true, opacity: 1.0 },
                { id: 'boundaryLayer', label: 'Cluster Boundaries', visible: true, opacity: 0.5 }
            ],
            showOpacity: options.showOpacity !== undefined ? options.showOpacity : true,
        };

        const layerIdsPresent = new Set(datamap.layers ? datamap.layers.map(layer => layer.id) : []);
        const currentLayers = this.options.layers.filter((layer) => layerIdsPresent.has(layer.id))
        this.options.layers.forEach(layer => {
            if (!layerIdsPresent.has(layer.id)) {
                console.warn(`LayerToggle: Layer with id "${layer.id}" not found in datamap. This layer will be ignored.`);
            }
        });
        this.options.layers = currentLayers;
        // Store layer states
        this.layerStates = new Map();
        this.options.layers.forEach(layer => {
            this.layerStates.set(layer.id, {
                visible: layer.visible,
                opacity: layer.opacity
            });
        });

        this.render();
        this.attachEventListeners();
        this.initializeLayers();
    }

    render() {
        this.container.innerHTML = '';

        // Title
        const title = document.createElement('div');
        title.className = 'layer-toggle-title';
        title.textContent = 'Map Layers';
        this.container.appendChild(title);

        // Layers list
        const layersList = document.createElement('div');
        layersList.className = 'layers-list';

        this.options.layers.forEach(layer => {
            const layerItem = document.createElement('div');
            layerItem.className = 'layer-item';
            layerItem.dataset.layerId = layer.id;

            // Visibility toggle
            const visibilityToggle = document.createElement('div');
            visibilityToggle.className = 'layer-visibility-toggle';

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.id = `layer-${layer.id}-visible`;
            checkbox.className = 'layer-checkbox';
            checkbox.checked = layer.visible;

            const checkboxLabel = document.createElement('label');
            checkboxLabel.htmlFor = `layer-${layer.id}-visible`;
            checkboxLabel.className = 'layer-label';
            checkboxLabel.textContent = layer.label;

            visibilityToggle.appendChild(checkbox);
            visibilityToggle.appendChild(checkboxLabel);
            layerItem.appendChild(visibilityToggle);

            // Opacity slider
            if (this.options.showOpacity) {
                const opacityControl = document.createElement('div');
                opacityControl.className = 'layer-opacity-control';

                const opacityLabel = document.createElement('span');
                opacityLabel.className = 'opacity-label';
                opacityLabel.textContent = 'Opacity:';

                const opacitySlider = document.createElement('input');
                opacitySlider.type = 'range';
                opacitySlider.id = `layer-${layer.id}-opacity`;
                opacitySlider.className = 'layer-opacity-slider';
                opacitySlider.min = '0';
                opacitySlider.max = '100';
                // Use square root to account for quadratic transform
                opacitySlider.value = String(Math.sqrt(layer.opacity) * 100);

                const opacityValue = document.createElement('span');
                opacityValue.className = 'opacity-value';
                opacityValue.id = `layer-${layer.id}-opacity-value`;
                opacityValue.textContent = `${Math.round(layer.opacity * 100)}%`;

                opacityControl.appendChild(opacityLabel);
                opacityControl.appendChild(opacitySlider);
                opacityControl.appendChild(opacityValue);
                layerItem.appendChild(opacityControl);
            }

            layersList.appendChild(layerItem);
        });

        this.container.appendChild(layersList);
    }

    attachEventListeners() {
        this.options.layers.forEach(layer => {
            // Visibility checkbox
            const checkbox = document.getElementById(`layer-${layer.id}-visible`);
            if (checkbox) {
                checkbox.addEventListener('change', (e) => {
                    this.setLayerVisibility(layer.id, e.target.checked);
                });
            }

            // Opacity slider
            if (this.options.showOpacity) {
                const slider = document.getElementById(`layer-${layer.id}-opacity`);
                const valueDisplay = document.getElementById(`layer-${layer.id}-opacity-value`);

                if (slider && valueDisplay) {
                    slider.addEventListener('input', (e) => {
                        const sliderValue = parseInt(e.target.value) / 100;
                        // Apply quadratic transform for better perceptual control
                        // This makes lower opacity values more responsive
                        const opacity = sliderValue * sliderValue;
                        valueDisplay.textContent = `${Math.round(opacity * 100)}%`;
                        this.setLayerOpacity(layer.id, opacity);
                    });
                }
            }
        });
    }

    initializeLayers() {
        // Apply initial layer states to the datamap
        this.options.layers.forEach(layer => {
            const state = this.layerStates.get(layer.id);
            this.applyLayerState(layer.id, state.visible, state.opacity);
        });
    }

    setLayerVisibility(layerId, visible) {
        const state = this.layerStates.get(layerId);
        if (state) {
            state.visible = visible;
            this.applyLayerState(layerId, visible, state.opacity);
        }
    }

    setLayerOpacity(layerId, opacity) {
        const state = this.layerStates.get(layerId);
        if (state) {
            state.opacity = opacity;
            this.applyLayerState(layerId, state.visible, opacity);
        }
    }

    applyLayerState(layerId, visible, opacity) {
        // Use datamap's layer management methods
        console.log(`Applying state for layer "${layerId}": visible=${visible}, opacity=${opacity}`);
        if (this.datamap.setLayerVisibility) {
            this.datamap.setLayerVisibility(layerId, visible);
        }
        if (this.datamap.setLayerOpacity) {
            this.datamap.setLayerOpacity(layerId, opacity);
        }
    }

    getLayerState(layerId) {
        return this.layerStates.get(layerId);
    }

    getAllLayerStates() {
        return Object.fromEntries(this.layerStates);
    }
}
