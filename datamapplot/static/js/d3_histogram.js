
const D3Histogram = (() => {
    /**
     * Checks if the input is a valid typed array.
     * 
     * @param {any} arr - The array to check.
     * @returns {boolean} True if the input is a typed array, otherwise false.
     * @private
     */
    isTypedArray = arr => {
        return arr instanceof Float32Array ||
            arr instanceof Float64Array ||
            arr instanceof Int8Array ||
            arr instanceof Uint8Array ||
            arr instanceof Uint8ClampedArray ||
            arr instanceof Int16Array ||
            arr instanceof Uint16Array ||
            arr instanceof Int32Array ||
            arr instanceof Uint32Array;
    }

    /**
     * Checks if an element of the provided data array is of a valid data type:
     * a number, string, Date object, or valid date string.
     * 
     * @param {Array} data - The data array to validate.
     * @returns boolean} True if the first element of the array is valid; false otherwise.
     * @private
     */
    isValidDataType = data => {
        return typeof data[0] === 'number' ||
            typeof data[0] === 'string' ||
            data[0] instanceof Date ||
            isValidDateStr(data[0]);
    };

    /**
     * Checks if the provided string can be converted into a valid Date object.
     * 
     * @param {string} dateStr - The string to check for validity as a date.
     * @returns {boolean} True if the string can be converted to a valid Date object, false otherwise.
     * @private
     */
    isValidDateStr = dateStr => !isNaN((new Date(dateStr)).getTime());

    /**
     * Builds a D3 histogram based on the provided data.
     * 
     * @property {Object} state - The state object holding the data, chart, peripherals, and interactions.
     */
    class D3Histogram {

        // Constants
        static DATA_TYPE_E = Object.freeze({
            NUMERICAL: 'number',
            CATEGORICAL: 'string',
            TEMPORAL: 'date'
        });

        static CLIP_BOUNDS_ID = "d3histogram-clipBounds";
        static BIN_RECT_CLASS_ID = "d3histogram-bin";
        static BIN_FOCUS_GROUP_ID = "d3histogram-focuscontainer";
        static BIN_FOCUS_RECT_CLASS_ID = "d3histogram-binFocus";
        static BIN_MIN_WIDTH = 10;
        static BIN_MAX_WIDTH = 30;
        static AXIS_CLASS_ID = 'd3histogram-axis';
        static XAXIS_GROUP_ID = 'd3histogram-xaxis';
        static YAXIS_GROUP_ID = 'd3histogram-yaxis';
        static XAXIS_TICKS_NB = 4;
        static YAXIS_TICKS_NB = 2;
        static INTERACTION_CONTAINER_ID = "d3histogram-interactioncontainer";

        /**
         * Static factory method for creating instances with validation.
         * 
         * @param {Array<string>} data - The data array containing the timestamps used to render the histogram.
         * @param {string} chartContainerId - The ID of the div to which the chart will be rendered.
         * @param {number} [chartWidth] - The width of the histogram chart.
         * @param {number} [chartHeight] - The height of the histogram chart.
         * @param {string} [title=''] - The title of the histogram chart.
         * @param {number} [binCount=-1] - The number of bins to use in the histogram. The number of bins to use in the histogram.
         * @param {string} [binDefaultFillColor="#6290C3"] - The default color for the histogram bins.
         * @param {string} [binSelectedFillColor="#2EBFA5"] - The color for the selected histogram bins.
         * @param {string} [binUnselectedFillColor="#9E9E9E"] - The color for the unselected histogram bins.
         * @param {string} [binContextFillColor="#E6E6E6"] - The color for the contextual histogram bins.
         * @param {boolean} [logScale=false] - Whether to use logarithmic scale for the y-axis.
         * @param {boolean} [enableClickPersistence=false] - Enable persistent selection when clicking on histogram bins.
         * @param {function} [chartSelectionCallback=() => {}] - A callback function that is invoked when a selection is made on the chart.
         * @returns {D3Histogram|null} A new instance of D3Histogram if no errors occur, otherwise null.
         * @static
         */
        static create({
            data,
            chartContainerId,
            chartWidth = 300,
            chartHeight = 70,
            title = '',
            binCount = -1,
            binDefaultFillColor = "#6290C3",
            binSelectedFillColor = "#2EBFA5",
            binUnselectedFillColor = "#9E9E9E",
            binContextFillColor = "#E6E6E6",
            logScale = false,
            enableClickPersistence = false,
            chartSelectionCallback = () => { }
        }) {

            // Parameter validation
            // if (!data || data.length === 0 || !(Array.isArray(data) || isTypedArray(data))) {
            //     console.error('Error: data must be a non-null, non-empty array.');
            //     return null;
            // }
            // if (!isValidDataType(data)){
            //     console.error("Invalid input type. Expected a number, string, Date, or valid date string.");
            //     return null;
            // }
            if (!chartContainerId) {
                console.error("Error: chart container ID was not provided.");
                return null;
            }

            try {
                return new D3Histogram({
                    data,
                    chartContainerId,
                    chartDimensions: {
                        width: chartWidth,
                        height: chartHeight,
                        margin: { top: 20, right: 5, bottom: 20, left: 20 }
                    },
                    title,
                    binCount,
                    binDefaultFillColor,
                    binSelectedFillColor,
                    binUnselectedFillColor,
                    binContextFillColor,
                    logScale,
                    enableClickPersistence,
                    chartSelectionCallback
                });
            } catch (error) {
                console.error("Error creating D3Histogram:", error);
                return null;
            }
        }

        /**
         * Constructor.
         * @private
         */
        constructor({
            data,
            chartContainerId,
            chartDimensions,
            title,
            binCount,
            binDefaultFillColor,
            binSelectedFillColor,
            binUnselectedFillColor,
            binContextFillColor,
            logScale,
            enableClickPersistence,
            chartSelectionCallback
        }) {
            // Define chart dimensions
            const { width, height, margin: { top, right, bottom, left } } = chartDimensions;
            const boundedWidth = width - left - right;
            const boundedHeight = height - top - bottom;

            // Store initial parameters and state
            this.state = {
                data: {
                    dataType: null,
                    rawData: data,
                    binsData: new Map(),
                    indicesData: new Int16Array(),
                    rawFocusData: null,
                    binsFocusData: null,
                    binCount: binCount != -1 ? binCount : null,
                    overallBinMin: null,
                    overallBinMax: null,
                },
                chart: {
                    chartContainerId: chartContainerId,
                    dimensions: {
                        ...chartDimensions,
                        boundedHeight,
                        boundedWidth
                    },
                    wrapper: null,
                    bounds: null,
                    binDefaultFillColor,
                    binSelectedFillColor,
                    binUnselectedFillColor,
                    binContextFillColor,
                    logScale,
                    binFocusDefaultFillColor: binDefaultFillColor,
                    binFocusSelectedFillColor: binSelectedFillColor,
                    binFocusUnselectedFillColor: binUnselectedFillColor,
                    chartSelectionCallback
                },
                peripherals: {
                    header: {
                        title: title.length !== 0 ? title : "DataMap Distribution",
                        subtitle: null,
                        titleDiv: null,
                        subtitleDiv: null,
                    },
                    axes: {
                        xAccessor: () => { },
                        yAccessor: () => { },
                        xScale: () => { },
                        yScale: () => { },
                        xAxis: () => { },
                        yAxis: () => { },
                        originalXScaleRange: null,
                    }
                },
                interactions: {
                    isBrushingActive: false,
                    brush: null,
                    prevBrushedDomain: null,
                    isPanningActive: false,
                    prevPanX: 0,
                    prevHoveredBinId: -1,
                    prevZoomK: 1,
                    isClickPersistenceEnabled: enableClickPersistence,
                    clickedBinId: -1,
                    isClickActive: false,
                    clickJustDeactivated: false
                }
            };

            // this.#parseData();
            this.#parseData();
            this.#drawCanvas();
            this.#drawChart();
            this.#initInteractions();
        }

        /**
         * Draws the chart based on the provided selected, focus indices.
         * It processes the focus data, and draws both the focus and context charts accordingly.
         * 
         * @param {Array<number>} selectedIndices - An array holding the selected indices.
         * @returns {undefined} No return value.
         */
        drawChartWithSelection(selectedIndices) {
            //Set focus
            this.#parseFocusData(selectedIndices);
            this.#drawFocusChart();

            //Set context
            this.#reset();
        }

        /**
         * Removes focus bounded data and bins, and resets context bins to their default state.
         * 
         * @returns {undefined} No return value.
        */
        removeChartWithSelection() {
            const { BIN_FOCUS_GROUP_ID: binsFocusGroupId } = D3Histogram;
            const { bounds } = this.state.chart;

            // Remove focus
            this.#clearFocusData();

            bounds.select(`#${binsFocusGroupId}`).remove();

            // Reset context
            this.#reset();
        }


        // **********************************************************************************
        //#region Data
        // **********************************************************************************

        #parseData() {
            const { DATA_TYPE_E } = D3Histogram;
            let { dataType } = this.state.data;
            let { binsData, indicesData } = this.state.data;
            const { rawData } = this.state.data;
            const { rawBinData, rawIndexData } = rawData;

            // Get data type, and aggregate the raw data based on its type
            const value = rawBinData[0].mean_value;

            if (typeof value === 'number') {
                dataType = DATA_TYPE_E.NUMERICAL;
            }
            else if (isValidDateStr(value)) {
                dataType = DATA_TYPE_E.TEMPORAL;
            }
            else {
                dataType = DATA_TYPE_E.CATEGORICAL;
            }

            rawBinData.forEach(bin => {
                const parsedBin = {
                    id: bin.id,
                    min: dataType === DATA_TYPE_E.TEMPORAL ? new Date(bin.min_value) : bin.min_value,
                    max: dataType === DATA_TYPE_E.TEMPORAL ? new Date(bin.max_value) : bin.max_value,
                    mean: dataType === DATA_TYPE_E.CATEGORICAL ? bin.id : bin.mean_value,
                    label: bin.mean_value,
                    indices: new Set(bin.indices)
                };
                binsData.set(bin.id, parsedBin);
            });

            indicesData = new Int16Array(rawIndexData["bin_id"]);

            this.state.data.dataType = dataType;
            this.state.data.binsData = binsData;
            this.state.data.indicesData = indicesData;
            this.state.data.binCount = binsData.size;
        }

        /**
         * Cleans and parses the selected data for use in the focus chart.
         * 
         * @param {Array<number>} selectedIndices - An array holding the indices of the selected data points.
         * @returns {undefined} No return value.
         * @private
        */
        #parseFocusData(selectedIndices) {
            const { binsData, indicesData } = this.state.data;

            // Set up focus raw data
            const rawFocusData = new Map();
            binsData.forEach(bin => {
                const focusBin = {
                    indices: new Set(),
                    binId: bin.id,
                    min: bin.min,
                    max: bin.max,
                    mean: bin.mean,
                    label: bin.label
                };
                rawFocusData.set(bin.id, focusBin);
            });

            // Use Set operations for faster lookups
            const selectedSet = new Set(selectedIndices);
            indicesData.forEach((binId, index) => {
                if (selectedSet.has(index)) {
                    const bin = rawFocusData.get(binId);
                    bin.indices.add(index);
                }
            });

            // Aggregate raw data based on its type
            const binsFocusData = rawFocusData;

            this.state.data.rawFocusData = rawFocusData;
            this.state.data.binsFocusData = binsFocusData;
        }

        /**
         * Clears current focus data.
         * 
         * @returns {undefined} No return value.
         * @private
        */
        #clearFocusData() {
            let { rawFocusData, binsFocusData } = this.state.data;

            rawFocusData = null;
            binsFocusData = null;

            this.state.data.rawFocusData = rawFocusData;
            this.state.data.binsFocusData = binsFocusData;
        }

        //#endregion Data



        // **********************************************************************************
        //#region Chart
        // **********************************************************************************
        /**
         * Draws chart canvas.
         * 
         * @returns {undefined} No return value.
         * @private
        */
        #drawCanvas() {
            const { chartContainerId, dimensions, } = this.state.chart;
            let { wrapper, bounds } = this.state.chart;

            wrapper = d3.select(`#${chartContainerId}`)
                .append("svg")
                .attr("width", dimensions.width)
                .attr("height", dimensions.height);

            bounds = wrapper.append("g")
                .style("transform", `translate(${dimensions.margin.left}px, ${dimensions.margin.top}px)`);

            this.state.chart.wrapper = wrapper;
            this.state.chart.bounds = bounds;
        }

        /**
         * Draws the chart.
         * 
         * @returns {undefined} No return value.
         * @private
        */
        #drawChart() {
            const {
                CLIP_BOUNDS_ID, BIN_RECT_CLASS_ID, AXIS_CLASS_ID, XAXIS_GROUP_ID, YAXIS_GROUP_ID,
                XAXIS_TICKS_NB, YAXIS_TICKS_NB
            } = D3Histogram;
            const { dimensions, chartContainerId, bounds, binDefaultFillColor, logScale } = this.state.chart;
            const { title } = this.state.peripherals.header;
            const binsData = Array.from(this.state.data.binsData.values());
            let { overallBinMin, overallBinMax } = this.state.data;

            // Define accessors & scales
            // --------------------------
            const xAccessor = d => d.mean;
            const yAccessor = d => d.indices.size;

            const xScale = d3.scaleBand()
                .domain(binsData.map(d => xAccessor(d)))
                .range([0, dimensions.boundedWidth])
                .padding(0.1);

            xScale.invert = function (_) {
                const scale = this;
                const domain = scale.domain;
                const paddingOuter = scale.paddingOuter();
                // const paddingInner = scale.paddingInner();
                const step = scale.step();

                const range = scale.range();
                var domainIndex,
                    n = domain().length,
                    reverse = range[1] < range[0],
                    start = range[reverse - 0],
                    stop = range[1 - reverse];

                if (_ < start + paddingOuter * step) domainIndex = 0;
                else if (_ > stop - paddingOuter * step) domainIndex = n - 1;
                else domainIndex = Math.floor((_ - start - paddingOuter * step) / step);

                return domain()[domainIndex];
            };

            let yScale = null;
            if (logScale) {
                yScale = d3.scaleSymlog()
                    .domain([0, d3.max(binsData, yAccessor)])
                    .range([dimensions.boundedHeight, 0]);
            } else {
                yScale = d3.scaleLinear()
                    .domain([0, d3.max(binsData, yAccessor)])
                    .range([dimensions.boundedHeight, 0]);
            }


            this.state.peripherals.axes.originalXScaleRange = xScale.range();
            this.state.peripherals.axes.xAccessor = xAccessor;
            this.state.peripherals.axes.yAccessor = yAccessor;
            this.state.peripherals.axes.xScale = xScale;
            this.state.peripherals.axes.yScale = yScale;

            // Draw data and peripherals
            // --------------------------
            bounds.append("defs")
                .append("clipPath")
                .attr("id", CLIP_BOUNDS_ID)
                .append("rect")
                .attr("width", dimensions.boundedWidth)
                .attr("height", dimensions.boundedHeight);

            // Bins for histogram
            const binsGroup = bounds.append("g");
            const binGroups = binsGroup.selectAll("g")
                .data(binsData)
                .join("g");
            const binRects = binGroups.append("rect")
                .attr("id", (_, i) => `${BIN_RECT_CLASS_ID}${i}`)
                .attr("class", BIN_RECT_CLASS_ID)
                .attr("x", d => xScale(xAccessor(d)))
                .attr("y", d => yScale(yAccessor(d)))
                .attr("width", xScale.bandwidth())
                .attr("height", d => dimensions.boundedHeight - yScale(yAccessor(d)))
                .attr("fill", binDefaultFillColor)
                .attr("clip-path", `url(#${CLIP_BOUNDS_ID})`);


            // Axes
            const yAxisTickFormat = d3.format(".1s");
            const yAxis = d3.axisRight(yScale)
                .ticks(logScale ? 2 * YAXIS_TICKS_NB : YAXIS_TICKS_NB)
                .tickFormat(d => d === yScale.domain()[0] ? '' : yAxisTickFormat(d));
            bounds.append("g")
                .attr("id", YAXIS_GROUP_ID)
                .attr("class", AXIS_CLASS_ID)
                .style("transform", `translate(-${dimensions.margin.left * .5}px, 0px)`)
                .call(yAxis);

            const xAxis = d3.axisBottom(xScale)
                .tickValues(this.#getAxisTickValues(xScale, XAXIS_TICKS_NB))
                .tickFormat(d => this.#getFormattedAxisTickValue(d));

            bounds.append("g")
                .attr("id", XAXIS_GROUP_ID)
                .attr("class", AXIS_CLASS_ID)
                .attr("transform", `translate(0,${dimensions.boundedHeight})`)
                .call(xAxis);


            // Title & subtitle
            const chartDiv = document.getElementById(chartContainerId);
            const titleDiv = document.createElement('div');
            titleDiv.id = "d3histogram-title";
            chartDiv.appendChild(titleDiv);

            d3.select(`#${titleDiv.id}`).html(`<b>${title}</b>`)

            const subtitleDiv = document.createElement('div');
            subtitleDiv.id = "d3histogram-subtitle";
            chartDiv.appendChild(subtitleDiv);

            // Reset bin min and max
            overallBinMin = Infinity;
            overallBinMax = -Infinity;
            binsData.forEach((binInfo, binId, map) => {
                const { min, max } = binInfo;
                overallBinMin = Math.min(overallBinMin, min);
                overallBinMax = Math.max(overallBinMax, max);
            });
            const subtitle = this.#getSubtitle([overallBinMin, overallBinMax]);
            d3.select(`#${subtitleDiv.id}`).html(subtitle);


            this.state.data.overallBinMin = overallBinMin;
            this.state.data.overallBinMax = overallBinMax;
            this.state.peripherals.axes.xAxis = xAxis;
            this.state.peripherals.axes.yAxis = yAxis;
            this.state.peripherals.header.title = title;
            this.state.peripherals.header.subtitle = subtitle;
            this.state.peripherals.header.titleDiv = titleDiv;
            this.state.peripherals.header.subtitleDiv = subtitleDiv;
        }

        /**
         * Draws the focus chart.
         * 
         * @returns {undefined} No return value.
         * @private
        */
        #drawFocusChart() {
            const { CLIP_BOUNDS_ID, BIN_FOCUS_GROUP_ID, BIN_FOCUS_RECT_CLASS_ID } = D3Histogram;
            const { xAccessor, yAccessor, xScale, yScale } = this.state.peripherals.axes;
            const { binFocusDefaultFillColor, dimensions, bounds } = this.state.chart;
            let binsFocusData = Array.from(this.state.data.binsFocusData.values());

            // Remove prior focus bins, if any
            bounds.select(`#${BIN_FOCUS_GROUP_ID}`).remove();

            // Draw focus bins
            const binsFocusGroup = bounds.append("g").attr("id", BIN_FOCUS_GROUP_ID);
            const binsFocusGroups = binsFocusGroup.selectAll("g")
                .data(binsFocusData)
                .join("g");
            const binFocusRects = binsFocusGroups.append("rect")
                .attr("id", (_, i) => `${BIN_FOCUS_RECT_CLASS_ID}${i}`)
                .attr("class", BIN_FOCUS_RECT_CLASS_ID)
                .attr("x", d => xScale(xAccessor(d)))
                .attr("y", d => yScale(yAccessor(d)))
                .attr("width", xScale.bandwidth())
                .attr("height", d => dimensions.boundedHeight - yScale(yAccessor(d)))
                .attr("fill", binFocusDefaultFillColor)
                .attr("clip-path", `url(#${CLIP_BOUNDS_ID})`);
        }

        /**
         * Checks if the focus chart is currently active.
         * 
         * @returns {boolean} True if the focus chart is active, otherwise false.
         * @private
         */
        #hasFocusChart = _ => this.state.data.rawFocusData !== null;

        /**
         * Resets the chart and peripherals to their default state.
         * 
         * @param {boolean} preserveClick - Whether to preserve click state during reset
         * @returns {undefined} No return value.
         * @private
         */
        #reset(preserveClick = false) {
            const {
                BIN_RECT_CLASS_ID, BIN_FOCUS_RECT_CLASS_ID,
                YAXIS_GROUP_ID, INTERACTION_CONTAINER_ID
            } = D3Histogram;
            const { overallBinMin, overallBinMax } = this.state.data;
            const { subtitleDiv } = this.state.peripherals.header;
            const { brush } = this.state.interactions;
            const {
                binDefaultFillColor, binContextFillColor,
                binFocusDefaultFillColor,
                chartSelectionCallback
            } = this.state.chart;
            let {
                isBrushingActive, prevBrushedDomain,
                isPanningActive, prevPanX,
                prevHoveredBinId,
                isClickActive, clickedBinId
            } = this.state.interactions;

            // If there's an active click and we want to preserve it, don't reset colors or callback
            if (preserveClick && isClickActive) {
                // Only reset interactions that are not click-related
                d3.select(`#${INTERACTION_CONTAINER_ID}`).call(brush.clear);
                prevBrushedDomain = null;
                isBrushingActive = false;
                isPanningActive = false;
                prevHoveredBinId = -1;
                prevPanX = 0;

                d3.select(`#${YAXIS_GROUP_ID}`).raise();
                d3.select(`#${INTERACTION_CONTAINER_ID}`).raise();

                this.state.interactions.isBrushingActive = isBrushingActive;
                this.state.interactions.prevBrushedDomain = prevBrushedDomain;
                this.state.interactions.prevHoveredBinId = prevHoveredBinId;
                this.state.interactions.isPanningActive = isPanningActive;
                this.state.interactions.prevPanX = prevPanX;
                return;
            }

            // Complete reset (original behavior)
            // Reset bins
            d3.selectAll(`.${BIN_RECT_CLASS_ID}`).style("fill", this.#hasFocusChart() ? binContextFillColor : binDefaultFillColor);
            d3.selectAll(`.${BIN_FOCUS_RECT_CLASS_ID}`).style("fill", binFocusDefaultFillColor);

            // Reset datamap plot
            chartSelectionCallback(null);

            // Reset subtitle
            let subtitle = this.#getSubtitle([overallBinMin, overallBinMax]);
            d3.select(`#${subtitleDiv.id}`).html(subtitle);

            // Reset interactions
            d3.select(`#${INTERACTION_CONTAINER_ID}`).call(brush.clear);
            prevBrushedDomain = null;
            isBrushingActive = false;
            isPanningActive = false;
            prevHoveredBinId = -1;
            prevPanX = 0;
            isClickActive = false;
            clickedBinId = -1;

            d3.select(`#${YAXIS_GROUP_ID}`).raise();
            d3.select(`#${INTERACTION_CONTAINER_ID}`).raise();

            this.state.interactions.isBrushingActive = isBrushingActive;
            this.state.interactions.prevBrushedDomain = prevBrushedDomain;
            this.state.interactions.prevHoveredBinId = prevHoveredBinId;
            this.state.interactions.isPanningActive = isPanningActive;
            this.state.interactions.prevPanX = prevPanX;
            this.state.interactions.isClickActive = isClickActive;
            this.state.interactions.clickedBinId = clickedBinId;
        }

        //#endregion Chart



        // **********************************************************************************
        //#region Interactions
        // **********************************************************************************

        /**
         * Initializes chart interactions: brush, hover, pan, and zoom.
         * 
         * @returns {undefined} No return value.
         * @private
        */
        #initInteractions() {
            const { INTERACTION_CONTAINER_ID, BIN_MAX_WIDTH } = D3Histogram;
            const { dimensions, bounds } = this.state.chart;
            const { binCount } = this.state.data;
            let { brush } = this.state.interactions;

            // Set brushing behavior
            brush = d3.brushX()
                .extent([[0, 0], [dimensions.boundedWidth, dimensions.boundedHeight]])
                .filter(event => {
                    // Allow brush only with Shift+click or drag, not with simple clicks
                    return event.shiftKey || event.type === 'mousedown' && event.detail > 1;
                })
                .on("brush", e => this.#handleBrush(e))
                .on("end", e => this.#handleBrushEnd(e));

            bounds.append("g")
                .attr("id", INTERACTION_CONTAINER_ID)
                .call(brush);

            // Set hovering behavior
            d3.select(`#${INTERACTION_CONTAINER_ID}`)
                .on('mousedown', e => this.#handleMouseDown(e))
                .on('mouseup', e => this.#handleMouseUp(e))
                .on('mousemove', e => this.#handleMouseMove(e))
                .on('mouseleave', e => this.#handleMouseLeave(e))
                .on('click', e => this.#handleClick(e));

            // Set zoom behavior
            const maxK = (binCount * BIN_MAX_WIDTH) / dimensions.boundedWidth;

            const zoom = d3.zoom()
                .scaleExtent([1, maxK])
                .translateExtent([[0, 0], [dimensions.boundedWidth, dimensions.boundedHeight]])
                .extent([[0, 0], [dimensions.boundedWidth, dimensions.boundedHeight]])
                .filter(event => event.type === 'wheel')
                .on("zoom", e => this.#handleZoom(e));

            d3.select(`#${INTERACTION_CONTAINER_ID}`).call(zoom);

            this.state.interactions.brush = brush;
        }

        /**
         * Handles the brush interaction on the chart.
         * 
         * This function is triggered when a brush event occurs. 
         * It updates the chart's bins and subtitle based on the brush selection,
         * and invokes the chart selection callback with the data bounded to the selected range.
         * 
         * @param {Object} e - The brush event object.
         * @returns {undefined} No return value.
         * @private
         */
        #handleBrush(e) {
            const { DATA_TYPE_E, BIN_RECT_CLASS_ID, BIN_FOCUS_RECT_CLASS_ID } = D3Histogram;
            const {
                binSelectedFillColor, binUnselectedFillColor, binContextFillColor,
                binFocusSelectedFillColor, binFocusUnselectedFillColor,
                chartSelectionCallback
            } = this.state.chart;
            const { xAccessor, xScale } = this.state.peripherals.axes;
            const { subtitleDiv } = this.state.peripherals.header;
            const { dataType, binsData, binsFocusData } = this.state.data;
            let { isBrushingActive, prevBrushedDomain } = this.state.interactions;

            if (dataType === DATA_TYPE_E.CATEGORICAL) { this.#removeBrush(); return; }
            if (!e.sourceEvent || !e.selection) { return; }

            isBrushingActive = true;
            const brushedDomain = e.selection.map(xScale.invert, xScale);

            // Locate brushed bins
            const data = this.#hasFocusChart() ? binsFocusData : binsData;

            const brushedDomainBinned = [Infinity, -Infinity];
            let brushedBins = [];
            data.forEach((d, i) => {
                if (xAccessor(d) >= brushedDomain[0] && xAccessor(d) <= brushedDomain[1]) {
                    brushedBins.push(d);

                    brushedDomainBinned[0] = Math.min(brushedDomainBinned[0], d.min);
                    brushedDomainBinned[1] = Math.max(brushedDomainBinned[1], d.max);
                }
            });
            const brushedBinIds = brushedBins.map(b => b.id);

            if (prevBrushedDomain != null &&
                prevBrushedDomain[0] === brushedDomainBinned[0] &&
                prevBrushedDomain[1] === brushedDomainBinned[1]) { return; }
            prevBrushedDomain = brushedDomainBinned;

            // Update bins
            d3.selectAll(`.${BIN_RECT_CLASS_ID}`)
                .style("fill", this.#hasFocusChart() ? binContextFillColor
                    : (_, i) => brushedBinIds.includes(i)
                        ? binSelectedFillColor : binUnselectedFillColor
                );

            d3.selectAll(`.${BIN_FOCUS_RECT_CLASS_ID}`)
                .style("fill", (_, i) => brushedBinIds.includes(i)
                    ? binFocusSelectedFillColor : binFocusUnselectedFillColor
                );

            // Update subtitle
            const subtitle = this.#getSubtitle(brushedDomainBinned);
            d3.select(`#${subtitleDiv.id}`).html(subtitle);

            // Update datamap plot
            let brushedIndices = new Set();
            brushedBins.forEach(b => {
                brushedIndices = brushedIndices.union(b.indices);
            });
            chartSelectionCallback(brushedIndices);

            this.state.interactions.isBrushingActive = isBrushingActive;
            this.state.interactions.prevBrushedDomain = prevBrushedDomain;
        }

        /**
         * Handles the end of the brush interaction on the chart.
         * If no selection is made (i.e., if the brush is cleared), it resets the chart to its default state.
         * 
         * @param {Object} e - The brush event object.
         * @returns {undefined} No return value.
         * @private
         */
        #handleBrushEnd(e) {
            const { DATA_TYPE_E } = D3Histogram;
            const { dataType } = this.state.data;

            if (dataType !== DATA_TYPE_E.CATEGORICAL && e.sourceEvent && !e.selection) {
                this.#reset();
            }
        }

        /**
         * Removes the visual elements within the brush container.
         * 
         * @returns {void} No return value
         * @private
         */
        #removeBrush() {
            const { INTERACTION_CONTAINER_ID } = D3Histogram;

            d3.select(`#${INTERACTION_CONTAINER_ID}`)
                .selectAll(".handle")
                .style("display", "none");

            d3.select(`#${INTERACTION_CONTAINER_ID}`)
                .selectAll(".selection")
                .style("display", "none");
        }

        /**
         * Handles the mouse down interaction on the chart.
         * It activates panning if the middle mouse button is pressed and brushing is not active.
         * 
         * @param {Object} e - The mouse event object.
         * @returns {void} No return value.
         * @private
         */
        #handleMouseDown(e) {
            const { isBrushingActive } = this.state.interactions;
            let { isPanningActive, prevPanX } = this.state.interactions;

            if (isBrushingActive || e.button != 1) { return; }

            isPanningActive = true;
            prevPanX = e.clientX;

            this.state.interactions.isPanningActive = isPanningActive;
            this.state.interactions.prevPanX = prevPanX;
        }


        /**
         * Handles the mouse up interaction on the chart.
         * It deactivates panning if the middle mouse button is released.
         * 
         * @param {Object} e - The mouse event object.
         * @returns {void} No return value.
         * @private
         */
        #handleMouseUp(e) {
            const { isBrushingActive } = this.state.interactions;
            let { isPanningActive, prevPanX } = this.state.interactions;

            if (isBrushingActive || e.button != 1) { return; }

            isPanningActive = false;

            this.state.interactions.isPanningActive = isPanningActive;
        }

        /**
         * Handles the mouse move interaction on the chart.
         * 
         * This function is triggered when the mouse enters or moves within the chart.
         * - If brushing is active, the function performs no action.
         * - If panning is active, it calls the panning handler.
         * - Otherwise, it calls the hovering handler.
         * 
         * @param {Object} e - The mouse event object.
         * @returns {undefined} No return value.
         * @private
         */
        #handleMouseMove(e) {
            const { isBrushingActive, isPanningActive } = this.state.interactions;

            if (isBrushingActive) { return; }

            if (isPanningActive) {
                this.#handlePan(e);
            }
            else {
                this.#handleHover(e);
            }
        }

        /**
         * Handles the mouse leave interaction on the chart. 
         * If brushing is not active, it resets the chart to its default state.
         * 
         * @param {Object} e - The mouse event object.
         * @returns {undefined} No return value.
         * @private
         */
        #handleMouseLeave(_) {
            const { isBrushingActive, isClickActive } = this.state.interactions;


            if (!isBrushingActive && !isClickActive) {

                this.#reset();
            } else {

            }
        }

        /**
        * Handles the hover interaction for the chart.
        * It updates the chart's bins and subtitle based on the current hovered bin, 
        * and invokes the chart selection callback with the data bounded to that bin.
        *
        * @param {Object} e - The mouse event object.
        * @returns {undefined} No return value.
        * @private
        */
        #handleHover(e) {
            const { BIN_RECT_CLASS_ID, BIN_FOCUS_RECT_CLASS_ID } = D3Histogram;
            const {
                binSelectedFillColor, binUnselectedFillColor, binContextFillColor,
                binFocusSelectedFillColor, binFocusUnselectedFillColor,
                chartSelectionCallback
            } = this.state.chart;
            const { xAccessor, xScale } = this.state.peripherals.axes;
            const { subtitleDiv } = this.state.peripherals.header;
            const { binsData, binsFocusData } = this.state.data;
            let { prevHoveredBinId, isClickActive, clickedBinId } = this.state.interactions;
            if (isClickActive || this.state.interactions.clickJustDeactivated) {
                return;
            }

            // Locate hovered bin
            const data = this.#hasFocusChart() ? binsFocusData : binsData;
            const xCoord = d3.pointer(e)[0];

            let hoveredBinId = -1;
            data.forEach((d, i) => {
                if (xCoord > xScale(xAccessor(d)) && xCoord <= xScale(xAccessor(d)) + xScale.bandwidth()) {
                    hoveredBinId = i;
                }
            });

            if (hoveredBinId === -1 || hoveredBinId === prevHoveredBinId) { return; }
            prevHoveredBinId = hoveredBinId;

            // Locate hovered bin
            const binClassId = this.#hasFocusChart() ? BIN_FOCUS_RECT_CLASS_ID : BIN_RECT_CLASS_ID;
            const hoveredBin = d3.select(`#${binClassId}${hoveredBinId}`).data()[0];

            // Update subtitle
            const subtitle = this.#getSubtitle([hoveredBin.min, hoveredBin.max]);
            d3.select(`#${subtitleDiv.id}`).html(subtitle);

            // Update bins
            d3.selectAll(`.${BIN_RECT_CLASS_ID}`)
                .style("fill", (_, i) => this.#hasFocusChart()
                    ? binContextFillColor
                    : i == hoveredBinId ? binSelectedFillColor : binUnselectedFillColor);

            d3.selectAll(`.${BIN_FOCUS_RECT_CLASS_ID}`)
                .style("fill", (_, i) => i == hoveredBinId ? binFocusSelectedFillColor : binFocusUnselectedFillColor);

            // Update datamap plot
            chartSelectionCallback(hoveredBin.indices);


            this.state.interactions.prevHoveredBinId = prevHoveredBinId;
        }

        /**
        * Handles the panning interaction for the chart.
        * It updates the chart's scales, axes, and bin positions based on mouse movement along the x direction. 
        *
        * @param {Object} e - The mouse event object.
        * @returns {undefined} No return value.
        * @private
        */
        #handlePan(e) {
            const { XAXIS_GROUP_ID, YAXIS_GROUP_ID, BIN_RECT_CLASS_ID, BIN_FOCUS_RECT_CLASS_ID } = D3Histogram;
            const { originalXScaleRange, xAccessor, yAccessor, xAxis, yAxis } = this.state.peripherals.axes;
            const { dimensions, wrapper } = this.state.chart;
            const { binsData } = this.state.data;
            let { xScale, yScale } = this.state.peripherals.axes;
            let { prevPanX } = this.state.interactions;

            // Calculate delta in x direction
            const dX = e.clientX - prevPanX;
            prevPanX = e.clientX;

            // Update x-scale and x-axis
            let pannedRange = xScale.range().map(d => d + dX);

            if (pannedRange[1] < originalXScaleRange[1]) {
                pannedRange = [pannedRange[0] + originalXScaleRange[1] - pannedRange[1], originalXScaleRange[1]];
            } else if (pannedRange[0] > originalXScaleRange[0]) {
                pannedRange = [originalXScaleRange[0], pannedRange[1] - pannedRange[0] - originalXScaleRange[0]];
            }

            xScale.range(pannedRange);
            wrapper.select(`#${XAXIS_GROUP_ID}`).call(xAxis);

            // Update y-scale and y-axis
            const pannedDomain = originalXScaleRange.map(xScale.invert, xScale);
            const pannedBinsData = Array.from(binsData.values()).filter(d => xAccessor(d) >= pannedDomain[0] && xAccessor(d) <= pannedDomain[1]);

            yScale.domain([0, d3.max(pannedBinsData, yAccessor)]);
            wrapper.select(`#${YAXIS_GROUP_ID}`)
                .transition()
                .call(yAxis);

            // Update bins
            wrapper.selectAll(`.${BIN_RECT_CLASS_ID}, .${BIN_FOCUS_RECT_CLASS_ID}`)
                .attr("x", d => xScale(xAccessor(d)))
                .transition()
                .attr("y", d => yScale(yAccessor(d)))
                .attr("height", d => dimensions.boundedHeight - yScale(yAccessor(d)));

            this.state.interactions.prevPanX = prevPanX;
        }

        /**
         * Handles the zoom interaction on the chart. 
         * It updates the chart's scales, axes, and bins when a zoom event occurs. 
         * 
         * @param {Object} e - The zoom event object containing the transform information.
         * @returns {undefined} No return value.
         * @private
         */
        #handleZoom(e) {
            const { isBrushingActive } = this.state.interactions;
            const { dimensions, wrapper } = this.state.chart;
            const { binsData } = this.state.data;
            const {
                XAXIS_GROUP_ID, YAXIS_GROUP_ID, XAXIS_TICKS_NB,
                BIN_RECT_CLASS_ID, BIN_FOCUS_RECT_CLASS_ID
            } = D3Histogram;
            const {
                originalXScaleRange, xAccessor, yAccessor,
                xScale, yScale, xAxis, yAxis
            } = this.state.peripherals.axes;
            let { prevZoomK } = this.state.interactions;

            if (isBrushingActive || e.sourceEvent.type !== "wheel" || prevZoomK == e.transform.k) return;
            prevZoomK = e.transform.k;

            // Update x-scale and x-axis
            xScale.range([0, dimensions.boundedWidth].map(d => e.transform.applyX(d)));

            xAxis.tickValues(this.#getAxisTickValues(xScale, XAXIS_TICKS_NB * e.transform.k));

            wrapper.select(`#${XAXIS_GROUP_ID}`)
                .transition()
                .call(xAxis);

            // Update y-scale and y-axis
            const zoomedDomain = originalXScaleRange.map(xScale.invert, xScale);
            const zoomedData = Array.from(binsData.values()).filter(d => xAccessor(d) >= zoomedDomain[0] && xAccessor(d) <= zoomedDomain[1]);

            yScale.domain([0, d3.max(zoomedData, yAccessor)]);
            wrapper.select(`#${YAXIS_GROUP_ID}`)
                .transition()
                .call(yAxis);

            // Update bins
            wrapper.selectAll(`.${BIN_RECT_CLASS_ID}, .${BIN_FOCUS_RECT_CLASS_ID}`)
                .transition()
                .attr("x", d => xScale(xAccessor(d)))
                .attr("y", d => yScale(yAccessor(d)))
                .attr("width", xScale.bandwidth())
                .attr("height", d => dimensions.boundedHeight - yScale(yAccessor(d)))

            this.state.interactions.prevZoomK = prevZoomK;
        }

        /**
         * Handles click events on histogram bins to enable selection/deselection functionality.
         * This method implements a toggle-based selection system where clicking a bin selects it,
         * and clicking the same bin again deselects it. Only one bin can be selected at a time.
         * 
         * @param {MouseEvent} e - The mouse click event object containing coordinates and target info
         * @returns {void} Returns early if click persistence is disabled or no bin is clicked
         */
        #handleClick(e) {

            const { isClickPersistenceEnabled } = this.state.interactions;
            if (!isClickPersistenceEnabled) return;

            const { BIN_RECT_CLASS_ID, BIN_FOCUS_RECT_CLASS_ID } = D3Histogram;
            const { chartSelectionCallback } = this.state.chart;
            const { xAccessor, xScale } = this.state.peripherals.axes;
            const { binsData, binsFocusData } = this.state.data;
            let { clickedBinId, isClickActive } = this.state.interactions;

            const data = this.#hasFocusChart() ? binsFocusData : binsData;
            const xCoord = d3.pointer(e)[0];

            let newClickedBinId = -1;
            data.forEach((d, i) => {
                if (xCoord > xScale(xAccessor(d)) && xCoord <= xScale(xAccessor(d)) + xScale.bandwidth()) {
                    newClickedBinId = i;
                }
            });

            if (newClickedBinId === -1) return;



            if (clickedBinId === newClickedBinId && isClickActive) {
                // Deselect: reset completely
                isClickActive = false;
                clickedBinId = -1;
                this.state.interactions.isClickActive = isClickActive;
                this.state.interactions.clickedBinId = clickedBinId;
                this.state.interactions.clickJustDeactivated = true;

                chartSelectionCallback(null);
                this.#reset();

                // Disable the flag after a brief period to allow normal hover
                setTimeout(() => {
                    this.state.interactions.clickJustDeactivated = false;
                }, 100);
            } else {
                // Select new bar: maintain click state
                isClickActive = true;
                clickedBinId = newClickedBinId;
                this.state.interactions.isClickActive = isClickActive;
                this.state.interactions.clickedBinId = clickedBinId;

                const binClassId = this.#hasFocusChart() ? BIN_FOCUS_RECT_CLASS_ID : BIN_RECT_CLASS_ID;
                const clickedBin = d3.select(`#${binClassId}${clickedBinId}`).data()[0];

                chartSelectionCallback(clickedBin.indices);
                this.#updateBinColors(clickedBinId);

                // Update subtitle to show the selected bar's range
                const { subtitleDiv } = this.state.peripherals.header;
                const subtitle = this.#getSubtitle([clickedBin.min, clickedBin.max]);
                d3.select(`#${subtitleDiv.id}`).html(subtitle);
            }


        }

        /**  
         * Updates the colors of histogram bins based on the selected bin ID.  
         *   
         * @param {number} selectedBinId - The ID of the bin that should be highlighted as selected  
         * @returns {void} No return value  
         * @private  
         */
        #updateBinColors(selectedBinId) {
            const { BIN_RECT_CLASS_ID, BIN_FOCUS_RECT_CLASS_ID } = D3Histogram;
            const {
                binSelectedFillColor, binUnselectedFillColor, binContextFillColor,
                binFocusSelectedFillColor, binFocusUnselectedFillColor
            } = this.state.chart;

            d3.selectAll(`.${BIN_RECT_CLASS_ID}`)
                .style("fill", (_, i) => this.#hasFocusChart()
                    ? binContextFillColor
                    : i == selectedBinId ? binSelectedFillColor : binUnselectedFillColor);

            d3.selectAll(`.${BIN_FOCUS_RECT_CLASS_ID}`)
                .style("fill", (_, i) => i == selectedBinId ? binFocusSelectedFillColor : binFocusUnselectedFillColor);
        }

        //#endregion Interactions



        // **********************************************************************************
        //#region  Peripherals
        // **********************************************************************************

        /**
         * Calculates the tick values for an axis based on the provided scale and the desired number of ticks.
         * 
         * @param {d3.Scale} scale - The D3 scale object
         * @param {number} numTicks - The desired number of ticks to be displayed on the axis.
         * @returns {Array} An array of tick values.
         * @private
         */
        #getAxisTickValues = (scale, numTicks) => {
            const domain = scale.domain();
            const ticksInterval = Math.max(1, Math.floor(domain.length / numTicks));

            let tickValues;
            if (domain.length <= numTicks) {
                tickValues = domain;
            } else {
                tickValues = domain.filter((_, i) => i % ticksInterval === 0);

                // Ensure exactly minimum number of tick values, adding the last number if needed
                while (tickValues.length < numTicks) {
                    tickValues.push(domain[domain.length - 1]);
                }
            }

            return tickValues;
        };

        /**
         * Formats an axis tick value based on its data type.
         * 
         * @param {number} value - The axis tick value to be formatted.
         * @returns {string} The formatted axis tick value.
         * @private
         */
        #getFormattedAxisTickValue(value) {
            const { DATA_TYPE_E } = D3Histogram;
            const { dataType } = this.state.data;

            let formattedValue = value;

            if (dataType === DATA_TYPE_E.NUMERICAL) {
                formattedValue = this.#formatNumericalValue(value);
            }
            else if (dataType === DATA_TYPE_E.CATEGORICAL) {
                formattedValue = this.#formatCategoricalValue(value);
            }
            else if (dataType === DATA_TYPE_E.TEMPORAL) {
                formattedValue = this.#formatTemporalValue(value);
            }

            return formattedValue;
        }

        /**
         * Generates a subtitle string based on the provided data range and its data type.
         * 
         * @param {Array} range - The range of values to be formatted.
         * @returns {string} A formatted subtitle string, or an empty string if the data type is categorical.
         * @private
         */
        #getSubtitle(range) {
            const { DATA_TYPE_E } = D3Histogram;
            const { dataType, binsData } = this.state.data;

            if (dataType === DATA_TYPE_E.CATEGORICAL) {
                return range[0] === range[1] ? `<b>${binsData.get(range[0]).label}</b>` : '';
            }

            let formattedRange = null;

            if (dataType === DATA_TYPE_E.NUMERICAL) {
                formattedRange = range.map(d => this.#formatNumericalValue(d));
            }
            else {
                formattedRange = range.map(d => this.#formatTemporalValue(d));
            }

            return `<b>${formattedRange[0]} — ${formattedRange[1]}</b>`;
        }

        /**
         * Formats a categorical value by trimming the input value after the first white space.
         * 
         * @param {string} value - The categorical value to be formatted.
         * @returns {string} The formatted categorical value.
         * @private
         */
        #formatCategoricalValue(value) {
            const { xAccessor } = this.state.peripherals.axes;
            const { binsData } = this.state.data;

            const tickBin = Array.from(binsData.values()).filter(b => xAccessor(b) === value)[0];
            const firstWhiteSpaceIndex = tickBin.label.indexOf(' ');

            return firstWhiteSpaceIndex !== -1 ? tickBin.label.slice(0, firstWhiteSpaceIndex) : tickBin.label;
        }

        /**
         * Formats a numerical value using SI prefixes.
         * 
         * @param {number} value - The numerical value to be formatted.
         * @returns {string} The formatted numerical value.
         * @private
         */
        #formatNumericalValue(value) {
            // Format with the SI prefixes
            const formatWithSI = d3.format(".4s");
            let formattedValue = formatWithSI(value);

            // Replace the 'µ' symbol with 'u' for micro, if any
            formattedValue = formattedValue.replace('µ', 'u');

            // Remove trailing zeros after the decimal point and the decimal point if not needed
            return formattedValue.replace(/(\.[0-9]*[1-9])0+|\.0*([a-zA-Z]*)$/, '$1$2');
        }

        /**
         * Formats a temporal value.
         * 
         * @param {Date|string} value - The temporal value to be formatted. It can be a Date object or a date string.
         * @returns {string} The formatted temporal value.
         * @private
         */
        #formatTemporalValue(value) {
            const formatTime = d3.utcFormat("%b %Y");
            return formatTime(new Date(value));
        }
        //#endregion  Peripherals

    }

    return D3Histogram;
})();