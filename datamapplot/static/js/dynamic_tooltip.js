
class DynamicTooltipManager {
    constructor(datamap, config) {
        this.config = {
            getIdentifier: ({ index }) => datamap?.metaData?.hover_text?.[index],
            fetchData: async (identifier) => { throw new Error("fetchData function not provided"); },
            formatContent: (data) => { throw new Error("formatContent function not provided"); },
            formatLoading: (identifier) => `<p>${identifier}</p>Loading ...`,
            formatError: (error, identifier) => `Error loading data for ${identifier}: ${error.message}`,

            tooltipStyle: `
                position: absolute;
                display: none;
                z-index: 1000;
                pointer-events: none;
                max-width: 300px;
            `,
            tooltipClassName: 'container-box deck-tooltip',
            initialHtml: '<p>Initializing...</p>',
            useCache: true,
            ...config // Override defaults with user-provided config
        };

        this.datamap = datamap;
        this.tooltipElement = null;
        this.currentIdentifier = null;
        this.cache = new Map();
        this.isFetching = false;

        this._createTooltipElement();
        this._bindDeckHandlers();
    }

    _createTooltipElement() {
        this.tooltipElement = document.createElement('div');
        this.tooltipElement.className = this.config.tooltipClassName;
        this.tooltipElement.style.cssText = this.config.tooltipStyle;
        this.tooltipElement.innerHTML = this.config.initialHtml;
        document.body.appendChild(this.tooltipElement);
    }

    _bindDeckHandlers() {
        const checkMetaDataAndBind = () => {
            if (this.datamap?.metaData) {
                this.datamap?.deckgl.setProps({
                    onHover: this._handleHover.bind(this),
                    getTooltip: null
                });
                if (this.tooltipElement.innerHTML === this.config.initialHtml) {
                   this.hide();
                }
            } else {
                setTimeout(checkMetaDataAndBind, 100); // Check again shortly
            }
        };
        checkMetaDataAndBind();
    }

    async _handleHover(info, event) {

        const identifier = this.config.getIdentifier(info);
        if (!identifier || info.index === undefined || info.index === null) {
            this.hide();
            this.currentIdentifier = null;
            return;
        }

        // Position Tooltip 
        // Use pointer coords for better positioning near the cursor
        const { x, y } = info;
        this.tooltipElement.style.left = `${x + 5}px`;
        this.tooltipElement.style.top = `${y + 5}px`;
        this.tooltipElement.style.display = 'block';
        this.tooltipElement.style.opacity = '1';


        // Handle Data Fetching
        if (identifier !== this.currentIdentifier) {
            this.currentIdentifier = identifier;
            this.isFetching = false;

            // Display loading state immediately
            this.tooltipElement.innerHTML = this.config.formatLoading(identifier);

            try {
                let data;
                // Check cache first if enabled
                if (this.config.useCache && this.cache.has(identifier)) {
                    data = this.cache.get(identifier);
                 } else {
                    if (this.isFetching) {
                        return;
                    }
                    this.isFetching = true;
                    // Fetch data using the provided function
                    data = await this.config.fetchData(identifier);
                    // Store in cache if enabled
                    if (this.config.useCache) {
                        this.cache.set(identifier, data);
                    }
                     this.isFetching = false;
                }

                if (this.currentIdentifier === identifier) {
                    const contentHtml = this.config.formatContent(data);
                    this.tooltipElement.innerHTML = contentHtml;
                }
            } catch (error) {
                 console.error(`ApiTooltipHandler: Error fetching/processing data for ${identifier}:`, error);
                 this.isFetching = false; // Release lock on error
                // Check if still hovering the item that caused the error
                if (this.currentIdentifier === identifier) {
                    this.tooltipElement.innerHTML = this.config.formatError(error, identifier);
                }
            }
        } else {
             // Ensure tooltip stays visible if hover continues on the same point
             if (this.tooltipElement.style.display === 'none') {
                 this.tooltipElement.style.display = 'block';
                 this.tooltipElement.style.opacity = '1';
             }
        }
    }

    // Public method to hide the tooltip
    hide() {
         if (this.tooltipElement && this.tooltipElement.style.display !== 'none') {
            this.tooltipElement.style.opacity = '0'; // Fade out
             setTimeout(() => {
                 if (this.tooltipElement.style.opacity === '0') {
                    this.tooltipElement.style.display = 'none';
                 }
             }, 150);
         }
    }

    // Public method to destroy the tooltip element
    destroy() {
        if (this.tooltipElement && this.tooltipElement.parentNode) {
            this.tooltipElement.parentNode.removeChild(this.tooltipElement);
            this.tooltipElement = null;
        }
        this.cache.clear();
    }
}