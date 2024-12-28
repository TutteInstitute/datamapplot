class Colorbar {
    constructor(container, options = {}) {
        this.container = container;
        this.options = {
            width: options.width || 40,
            height: options.height || 300,
            min: options.min || 0,
            max: options.max || 100,
            numTicks: options.numTicks || 5,
            colormap: options.colormap || ['blue', 'red'],
            label: options.label || ''
        };
        this.render();
    }

    createColorScale() {
        const { colormap } = this.options;
        if (colormap.length === 0) return 'none';
        if (colormap.length === 1) return colormap[0];

        return `linear-gradient(to top, ${colormap.join(', ')})`;
    }

    generateTicks() {
        const { min, max, numTicks } = this.options;
        const ticks = [];
        for (let i = numTicks - 1; i >= 0; i--) {
            const value = min + (i / (numTicks - 1)) * (max - min);
            const position = 100 - (i / (numTicks - 1) * 100);
            ticks.push({
                value: value.toFixed(1),
                position
            });
        }
        return ticks;
    }

    render() {
        // Create container
        const wrapper = document.createElement('div');
        wrapper.className = 'colorbar-container';

        // Create colorbar
        const colorbar = document.createElement('div');
        colorbar.className = 'colorbar';
        colorbar.style.background = this.createColorScale();

        // Create tick container
        const tickContainer = document.createElement('div');
        tickContainer.className = 'tick-container';

        // Add ticks
        const ticks = this.generateTicks();
        ticks.forEach(tick => {
            const tickElement = document.createElement('div');
            tickElement.className = 'tick';
            tickElement.style.top = `${tick.position}%`;

            const tickLine = document.createElement('div');
            tickLine.className = 'tick-line';

            const tickLabel = document.createElement('div');
            tickLabel.className = 'tick-label';
            tickLabel.textContent = tick.value;

            tickElement.appendChild(tickLine);
            tickElement.appendChild(tickLabel);
            tickContainer.appendChild(tickElement);
        });

        // Add label if provided
        if (this.options.label) {
            const label = document.createElement('div');
            label.style.writingMode = 'vertical-rl';
            label.style.transform = 'rotate(180deg)';
            label.style.marginRight = '8px';
            label.textContent = this.options.label;
            wrapper.appendChild(label);
        }

        wrapper.appendChild(colorbar);
        wrapper.appendChild(tickContainer);
        this.container.appendChild(wrapper);
    }
}

function convertRGBtoObj(colorString) {
  const rgbKeys = ['r', 'g', 'b', 'a'];
  let rgbObj = {};
  let color = colorString.replace(/^rgba?\(|\s+|\)$/g,'').split(',');

  for (let i in rgbKeys)
    rgbObj[rgbKeys[i]] = parseInt(color[i]) || 1;

  return rgbObj;
}

class ColorLegend {
    constructor(container, datamap, colorData, colorField, options = {}) {
        this.container = container;
        this.options = {
            width: options.width || 400,
            colormap: options.colormap || { "High": "blue", "Low": "red" },
            label: options.label || ''
        };
        this.datamap = datamap;
        this.colorData = colorData;
        this.colorField = colorField;
        this.selectedItems = new Set();
        this.render();
    }

    render() {
        for (const [label, color] of Object.entries(this.options.colormap)) {
            const legendItem = document.createElement('div');
            legendItem.className = 'legend-item';

            const colorBox = document.createElement('div');
            colorBox.className = 'color-swatch-box';
            colorBox.style.borderRadius = "2px";
            colorBox.style.backgroundColor = color;

            const labelElement = document.createElement('div');
            labelElement.className = 'legend-label';
            labelElement.textContent = label;

            legendItem.appendChild(colorBox);
            legendItem.appendChild(labelElement);
            this.container.appendChild(legendItem);
        }
        this.container.addEventListener('click', (event) => {
            const selection = event.srcElement.style.backgroundColor;
            if (selection) {
                if (this.selectedItems.has(selection)) {
                    this.selectedItems.delete(selection);
                    event.srcElement.innerHTML = "";
                } else {
                    this.selectedItems.add(selection);
                    event.srcElement.innerHTML = "●";
                }
                const selectedIndices = [];
                this.selectedItems.forEach((color) => {
                    const selectedColor = convertRGBtoObj(color);
                    for (let i = 0; i < this.colorData[`${this.colorField}_r`].length; i++) {;
                        if (this.colorData[`${this.colorField}_r`][i] === selectedColor.r &&
                            this.colorData[`${this.colorField}_g`][i] === selectedColor.g && 
                            this.colorData[`${this.colorField}_b`][i] === selectedColor.b) {
                            selectedIndices.push(i);
                        }
                    }
                });
                this.datamap.addSelection(selectedIndices, "legend");
            }
        });
    }
}

class ColormapSelectorTool {

    constructor(colorMaps, colorMapContainer, colorData, legendContainer, datamap, nColors = 5) {
        this.colorMaps = colorMaps;
        this.colorMapContainer = colorMapContainer;
        this.colorData = colorData;
        this.datamap = datamap;
        this.nColors = nColors;
        this.legendContainer = legendContainer;

        // Handle color map item selection
        this.selectedColorMap = colorMaps[0];

        // Create a temporary div to measure option widths
        this.measureDiv = document.createElement("div");
        this.measureDiv.style.position = "absolute";
        this.measureDiv.style.visibility = "hidden";
        this.measureDiv.style.whiteSpace = "nowrap";
        document.body.appendChild(this.measureDiv);

        // Calculate the maximum width before creating the dropdown
        const maxWidth = this.calculateMaxWidth();

        // Create the required DOM elements
        this.colorMapDropdown = document.createElement("div");
        this.colorMapDropdown.className = "color-map-dropdown";
        this.colorMapDropdown.style.width = `${maxWidth}px`;

        const colorMapSelected = document.createElement("div");
        colorMapSelected.className = "color-map-selected";
        this.selectedColorSwatch = document.createElement("span");
        this.selectedColorSwatch.className = "color-swatch";
        this.selectedColorSwatch.id = "selectedColorSwatch";
        colorMapSelected.appendChild(this.selectedColorSwatch);

        this.selectedColorMapText = document.createElement("span");
        this.selectedColorMapText.className = "color-map-text";
        this.selectedColorMapText.id = "selectedColorMapText";
        colorMapSelected.appendChild(this.selectedColorMapText);

        const downArrow = document.createElement("span");
        downArrow.className = "dropdown-arrow";
        downArrow.innerHTML = "▼";
        colorMapSelected.appendChild(downArrow);
        this.colorMapDropdown.appendChild(colorMapSelected);

        this.colorMapOptions = document.createElement("div");
        this.colorMapOptions.className = "color-map-options";
        this.colorMapOptions.id = "colorMapOptions";
        this.colorMapOptions.style.display = 'none';
        this.colorMapOptions.style.width = `${maxWidth}px`;

        this.colorMapDropdown.appendChild(this.colorMapOptions);
        this.colorMapContainer.appendChild(this.colorMapDropdown);

        // Attach event listeners
        this.colorMapDropdown.addEventListener('click', (e) => { this.colorMapOptions.style.display = this.colorMapOptions.style.display === 'none' ? 'block' : 'none' });


        // Initial setup
        this.updateSelectedColorMap();
        this.populateColorMapOptions();

        // Clean up measurement div
        document.body.removeChild(this.measureDiv);
    }

    calculateMaxWidth() {
        let maxWidth = 0;

        // Create a sample option with the same styling
        this.measureDiv.className = "color-map-option";

        // Measure each option
        for (const colorMap of this.colorMaps) {
            this.measureDiv.innerHTML = `${this.createColorSwatch(colorMap.colors)} <span class="color-map-text">${colorMap.field} - ${colorMap.description}</span>`;
            const width = this.measureDiv.offsetWidth + 40; // Add padding for arrow and borders
            maxWidth = Math.max(maxWidth, width);
        }

        return maxWidth;
    }

    // Create a color swatch
    createColorSwatch(colors, categorical = false) {
        const n = Math.min(this.nColors, colors.length);
        var result = '<span class="color-swatch">'
        if (colors.length > 16 && !categorical) {
            // Long color maps are likely continuous so sample uniformly across the range
            const stepSize = (colors.length - 1) / (n - 1);
            for (let i = 0; i < colors.length; i += stepSize) {
                result += `<span class="color-swatch-box"; style="background: ${colors[Math.round(i)]}"></span>`
            }
        } else {
            // Short color maps are likely categorical and we can just take the first nColors elements
            for (let i = 0; i < n; i++) {
                result += `<span class="color-swatch-box"; style="background: ${colors[Math.round(i)]}"></span>`
            }
        }
        result += '</span>'
        return result;
    }


    handleColorMapSelection(colorMap) {
        this.selectedColorMap = colorMap;
        this.updateSelectedColorMap();

        // Dispatch recolor to the datamap
        if (colorMap.field === 'none') {
            this.datamap.resetPointColors();
            this.legendContainer.style.display = 'none';
        } else {
            this.datamap.recolorPoints(this.colorData, colorMap.field);
            if ((colorMap.kind === "categorical") && (colorMap.colors.length < 20) && Object.hasOwn(colorMap, "colorMapping")) {
                this.legendContainer.innerHTML = '';
                //console.log(colorMap.colorMapping);
                new ColorLegend(this.legendContainer, this.datamap, this.colorData, colorMap.field, { colormap: colorMap.colorMapping });
                this.legendContainer.style.display = 'block';
            } else if (colorMap.kind === "continuous") {
                this.legendContainer.innerHTML = '';
                //console.log(colorMap.colors, colorMap.description, colorMap.valueRange);
                new Colorbar(this.legendContainer, { colormap: colorMap.colors, label: colorMap.description, min: colorMap.valueRange[0], max: colorMap.valueRange[1] });
                this.legendContainer.style.display = 'block';
            } else {
                this.legendContainer.style.display = 'none';
            }
        }
    }

    updateSelectedColorMap() {
        this.selectedColorSwatch.innerHTML = (this.createColorSwatch(this.selectedColorMap.colors, this.selectedColorMap.kind === "categorical"));
        this.selectedColorMapText.innerHTML = this.selectedColorMap.description;
    }

    populateColorMapOptions() {
        for (const colorMap of this.colorMaps) {
            const colorMapOption = document.createElement("div");
            colorMapOption.className = "color-map-option";
            colorMapOption.addEventListener('click', (event) => { this.handleColorMapSelection(colorMap) });
            colorMapOption.innerHTML = `${this.createColorSwatch(colorMap.colors, colorMap.kind === "categorical")} <span class="color-map-text">${colorMap.description}</span>`;
            this.colorMapOptions.appendChild(colorMapOption);
        }
    }
}