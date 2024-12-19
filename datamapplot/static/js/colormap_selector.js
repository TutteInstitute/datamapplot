class ColormapSelector {

    constructor(colorMaps, colorMapContainer, colorData, datamap) {
        this.colorMaps = colorMaps;
        this.colorMapContainer = colorMapContainer;
        this.colorData = colorData;
        this.datamap = datamap;

        // Handle color map item selection
        this.selectedColorMap = colorMaps[0];

        // Create the required DOM elements
        this.colorMapDropdown = document.createElement("div");
        this.colorMapDropdown.className = "color-map-dropdown";
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

        this.colorMapDropdown.appendChild(this.colorMapOptions);
        this.colorMapContainer.appendChild(this.colorMapDropdown);

        // Attach event listeners
        this.colorMapDropdown.addEventListener('click', (e) => { this.colorMapOptions.style.display = this.colorMapOptions.style.display === 'none' ? 'block' : 'none' });


        // Initial setup
        this.updateSelectedColorMap();
        this.populateColorMapOptions();
    }

    // Create a color swatch
    createColorSwatch(colors, nColors = 5) {
        const n = Math.min(nColors, colors.length);
        var result = '<span class="color-swatch">'
        if (colors.length > 16) {
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
        if (colorMap.field === 'None') {
            this.datamap.resetPointColors();
        } else {
            this.datamap.recolorPoints(this.colorData, colorMap.field);
        }
    }

    updateSelectedColorMap() {
        this.selectedColorSwatch.innerHTML = (this.createColorSwatch(this.selectedColorMap.colors));
        this.selectedColorMapText.innerHTML = (`${this.selectedColorMap.field} - ${this.selectedColorMap.description}`);
    }

    populateColorMapOptions() {
        for (const colorMap of this.colorMaps) {
            const colorMapOption = document.createElement("div");
            colorMapOption.className = "color-map-option";
            colorMapOption.addEventListener('click', (event) => { this.handleColorMapSelection(colorMap) });
            colorMapOption.innerHTML = `${this.createColorSwatch(colorMap.colors)} <span class="color-map-text">${colorMap.field} - ${colorMap.description}</span>`;
            this.colorMapOptions.appendChild(colorMapOption);
        }
    }
}