
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
            NUMERICAL : 'number',
            CATEGORICAL : 'string',
            TEMPORAL : 'date'
        });

        static CLIP_BOUNDS_ID = "d3histogram-clipBounds";
        static BIN_RECT_CLASS_ID = "d3histogram-bin";
        static BIN_FOCUS_GROUP_ID = "d3histogram-focuscontainer";
        static BIN_FOCUS_RECT_CLASS_ID = "d3histogram-binFocus";
        static BIN_MIN_WIDTH = 10;
        static BIN_MAX_WIDTH = 30;
        static AXIS_CLASS_ID  = 'd3histogram-axis';
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
            chartSelectionCallback = () => {}
        }) {

            // Parameter validation
            if (!data || data.length === 0 || !(Array.isArray(data) || isTypedArray(data))) {
                console.error('Error: data must be a non-null, non-empty array.');
                return null;
            }
            if (!isValidDataType(data)){
                console.error("Invalid input type. Expected a number, string, Date, or valid date string.");
                return null;
            }
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
                    indicesData: new Map(),
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
                        xAccessor: () => {},
                        yAccessor: () => {},
                        xScale: () => {},
                        yScale: () => {},
                        xAxis: () => {},
                        yAxis: () => {},
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
                    prevZoomK: 1
                }
            };
            
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
        
        /**
         * Bins numerical data.
         * 
         * This function taskes an array of numerical data and assigns each data point to the
         * corresponding bin. If there is no user-specified number of bins, this function 
         * calculates the appropriate number of bins based on the chart dimensions.
         * 
         * @param {Array<number>} numArray - An array of numerical data to be binned.
         * @returns {undefined} No return value.
         * @private
         */
        #binNumericalData(numArray) {
            const { BIN_MIN_WIDTH } = D3Histogram;
            const { dimensions } = this.state.chart;
            let { binsData, indicesData, binCount } = this.state.data;

            // Get number of bins
            binCount = binCount ?? Math.ceil(dimensions.boundedWidth / BIN_MIN_WIDTH);

            // Find the minimum and maximum values in the array
            let minVal = Infinity;
            let maxVal = -Infinity;
            
            for (let value of numArray) {
                if (value < minVal) minVal = value;
                if (value > maxVal) maxVal = value;
            }
    
            // Calculate the bin size
            const binSize = (maxVal - minVal) / binCount;
    
            // Initialize the bins array
            binsData = Array.from({ length: binCount }, (_, i) => {
                const min = minVal + i * binSize;
                const max = minVal + (i + 1) * binSize;
                const mean = (minVal + i * binSize + minVal + (i + 1) * binSize) / 2;

                return {
                    id: i,
                    values: [],
                    indices: [],
                    min: min,
                    max: max,
                    mean: mean,
                    label: mean
            }});
            indicesData = Array.from({ length: numArray.length }, () => ({ binId: null, value: null }));
    
            // Iterate over the values and assign them to the appropriate bin
            numArray.forEach((value, i) => {
                const binIndex = Math.min(
                    Math.floor((value - minVal) / binSize),
                    binCount - 1 // Ensure the value goes into the last bin if it's the maximum value
                );
                const bin = binsData[binIndex];
                bin.values.push(value);
                bin.indices.push(i);

                indicesData[i] = { binId: binIndex, value: value };              
            });
    
            this.state.data.binsData = binsData;
            this.state.data.indicesData = indicesData;
            this.state.data.binCount = binsData.length;
        }

        /**
         * Bins categorical data.
         * This function takes an array of categorical data, identifies unique categories, and 
         * bins the data accordingly. If a user-specified number of bins is provided, it is overridden 
         * to match the number of unique categories.
         * 
         * @param {Array} categoryArray - An array of categorical data to be binned.
         * @returns {undefined} No return value.
         * @private
         */
        #binCategoricalData(categoryArray) {
            let { binsData, indicesData, binCount } = this.state.data;

            // Find the unique categories
            const uniqueCategories = [...new Set(categoryArray)];
    
            // Initialize bins
            binsData = uniqueCategories.map((category, i) => ({
                id: i,
                label: category,
                indices: [],
                values: [],
                min: i,
                max: i,
                mean: i
            }));
            indicesData = Array.from({ length: categoryArray.length }, () => ({ binId: null, value: null }));
    
            // Create a map for quick lookup of bin indices by category
            const categoryToBinId = {};
            uniqueCategories.forEach((category, i) => {
                categoryToBinId[category] = i;
            });
    
            // Iterate over the category array and assign each one to the corresponding bin
            categoryArray.forEach((category, i) => {
                const binId = categoryToBinId[category];
                binsData[binId].indices.push(i);
                binsData[binId].values.push(category);
    
                indicesData[i] ={ binId: binId, value: category };
            });

            this.state.data.binsData = binsData;
            this.state.data.indicesData = indicesData;
            this.state.data.binCount = binsData.length;
        }

        /**
         * Bins temporal data.
         * If no user-specified number of bins is provided, this function aggregates dates by year.
         * 
         * @param {Array<string>} dateArray - Array of date strings
         * @returns {void} No return value
         * @private
         */
        #binTemporalData(dateArray) {
            let { binsData, indicesData, binCount } = this.state.data;

            if (!binCount) {
                this.#binTemporalDataByYear(dateArray);
                return;
            }
    
            // Parse and filter out invalid dates
            const validDates = this.#parseAndFilterDates(dateArray);

            // Sort valid dates chronologically
            validDates.sort((a, b) => a.date - b.date);

            // Determine the overall date/bin range
            const overallMin = validDates[0].date;
            const overallMax = validDates[validDates.length - 1].date;
            const timeSpan = overallMax - overallMin;
            const binRange = timeSpan / binCount;

            // Initialize bins
            indicesData = Array.from({ length: dateArray.length }, () => ({ binId: null, value: null }));

            binsData = Array.from({ length: binCount }, (_, binId) => {
                const min = overallMin.getTime() + binId * binRange;
                const max = min + binRange;
                const mean = (min + max) / 2;
                const label = new Date(mean);

                return {
                    binId,
                    indices: [],
                    values: [],
                    min,
                    max,
                    mean,
                    label
                };
            });
            
            // Assign dates to bins
            validDates.forEach((item, _) => {
                const binIndex = Math.floor((item.date - overallMin) / binRange);
                const bin = binsData[Math.min(binIndex, binCount - 1)];

                bin.indices.push(item.index);
                bin.values.push(item.date);
                indicesData[item.index] = { binId: bin.binId, value: item.date };
            });

            this.state.data.binsData = binsData;
            this.state.data.indicesData = indicesData;
            this.state.data.binCount = binsData.length;            
        }

        /**
         * Bins temporal data by year.
         * 
         * @param {Array<string>} dateArray - Array of date strings
         * @returns {void} No return value
         * @private
         */
        #binTemporalDataByYear(dateArray) {
            let { binsData, indicesData, binCount } = this.state.data;
        
            // Parse and filter out invalid dates
            const validDates = this.#parseAndFilterDates(dateArray);
            
            // Parse the input dates and group them by year (in UTC)
            const datesByYear = validDates.reduce((acc, { date, index }) => {
                const year = date.getUTCFullYear();
                if (!acc[year]) {
                    acc[year] = [];
                }
                acc[year].push({ date, index });
                return acc;
            }, {});
        
            // Extract the unique years and sort them
            const uniqueYears = Object.keys(datesByYear).map(Number).sort((a, b) => a - b);

            // Ensure all years between the earliest and latest year are included
            const earliestYear = uniqueYears[0];
            const latestYear = uniqueYears[uniqueYears.length - 1];
            const allYears = [];
            for (let year = earliestYear; year <= latestYear; year++) {
                allYears.push(year);
                if (!datesByYear[year]) {
                    datesByYear[year] = [];
                }
            }
        
            // Determine number of bins
            binCount = allYears.length;

            // Initialize binsData and indicesData as Maps
            indicesData = new Map();
            binsData = new Map();

            allYears.forEach((year, binIndex) => {
                const min = Date.UTC(year, 0, 1);
                const max = Date.UTC(year, 11, 31);
                const mean = (min + max) / 2;
                const label = new Date(mean);

                const bin = {
                    id: binIndex,
                    values: [],
                    indices: new Set(),
                    min,
                    max,
                    mean,
                    label
                };     
                datesByYear[year].forEach(({ date, index }) => {
                    bin.values.push(date);
                    bin.indices.add(index);
                    indicesData.set(index, { binId: binIndex, value: date });
                });
        
                // Sort dates in the bin (based on UTC time)
                bin.values.sort((a, b) => a.getTime() - b.getTime());     

                binsData.set(binIndex, bin);
            });
            
            this.state.data.binsData = binsData;
            this.state.data.indicesData = indicesData;
            this.state.data.binCount = binsData.size;
        }

        /**
         * Parses date strings into Date objects.
         * 
         * @param {Array<string>} dateArray - Array of date strings
         * @returns {Array<Object>} - Array of valid date objects with associated indices
         */
        #parseAndFilterDates = dateArray => {
            const parseDate = d3.utcParse("%Y-%m-%d");
            return dateArray
                .filter(dateStr => !isNaN((new Date(dateStr)).getTime()))
                .map((dateStr, index) => ({ dateStr, date: parseDate(dateStr), index }));
        };

        /**
         * Cleans and parses the original, raw data for use in the chart.
         * 
         * @returns {undefined} No return value.
         * @private
        */
        #parseData() {
            const { DATA_TYPE_E } = D3Histogram;
            const { rawData } = this.state.data;
            let { dataType } = this.state.data;

            // Get data type, and aggregate the raw data based on its type
            const value = rawData[0];

            if (typeof value === 'number') { 
                dataType = DATA_TYPE_E.NUMERICAL;
                this.#binNumericalData(rawData);
            }
            else if (isValidDateStr(value)) { 
                dataType = DATA_TYPE_E.TEMPORAL;
                this.#binTemporalData(rawData);
            }
            else {
                dataType = DATA_TYPE_E.CATEGORICAL; 
                this.#binCategoricalData(rawData);
            }

            this.state.data.dataType = dataType;
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
        
            // Use a Map to quickly lookup bins
            const rawFocusData = new Map(binsData);
            rawFocusData.forEach(bin => {
                bin.indices = new Set();
                bin.values = [];
            });
    
            // Use Set operations for faster lookups
            const selectedSet = new Set(selectedIndices);
            for (const [index, { binId, value }] of indicesData) {
                if (selectedSet.has(index)) {
                    const bin = rawFocusData.get(binId);
                    bin.indices.add(index);
                    bin.values.push(value);
                }
            }
    
            this.state.data.rawFocusData = rawFocusData;
            this.state.data.binsFocusData = rawFocusData;            
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
            const { chartContainerId, dimensions,  } = this.state.chart;
            let { wrapper , bounds } = this.state.chart;

            wrapper = d3.select(`#${chartContainerId}`)
                .append("svg")
                .attr("width", dimensions.width)
                .attr("height", dimensions.height);

            bounds = wrapper.append("g")
                .style("transform", `translate(${dimensions.margin.left}px, ${dimensions.margin.top}px)`);

            this.state.chart.wrapper = wrapper;
            this.state.chart.bounds = bounds;
        }
        
        #updateAxes(xScale, yScale, xTicksCount, yTicksCount) {
            const { XAXIS_GROUP_ID, YAXIS_GROUP_ID, XAXIS_TICKS_NB, YAXIS_TICKS_NB, AXIS_CLASS_ID } = D3Histogram;
            const { bounds, dimensions, chartContainerId } = this.state.chart;
            const { title } = this.state.peripherals.header;
            const { binsData } = this.state.data;
            // let { overallBinMin, overallBinMax } = this.state.data;

            const yAxisTickFormat = d3.format(".1s");
            const yAxis = d3.axisRight(yScale)
                .ticks(YAXIS_TICKS_NB)
                .tickFormat(d => d === yScale.domain()[0] ? '' : yAxisTickFormat(d));
            bounds.append("g")
                .attr("id", YAXIS_GROUP_ID)
                .attr("class", AXIS_CLASS_ID)
                .style("transform", `translate(-${dimensions.margin.left*.5}px, 0px)`)
                .call(yAxis);

            const xAxis = d3.axisBottom(xScale)
                .tickValues(this.#getAxisTickValues(xScale, XAXIS_TICKS_NB))
                .tickFormat(d => this.#getFormattedAxisTickValue(d));
    
            bounds.select(`#${XAXIS_GROUP_ID}`)
                .attr("transform", `translate(0, ${dimensions.boundedHeight})`)
                .call(xAxis);
    
            bounds.select(`#${YAXIS_GROUP_ID}`)
                .call(yAxis);

            // Title & subtitle
            const chartDiv = document.getElementById(chartContainerId);
            const titleDiv = document.createElement('div');
            titleDiv.id = "d3histogram-title";
            chartDiv.appendChild(titleDiv);

            d3.select(`#${titleDiv.id}`).html(`<b>${title}</b>`)

            const subtitleDiv = document.createElement('div');
            subtitleDiv.id = "d3histogram-subtitle";
            chartDiv.appendChild(subtitleDiv);

            let overallBinMin = Infinity;
            let overallBinMax = -Infinity;
            binsData.forEach((binInfo, binId, map) => {
                const { min, max } = binInfo;
                overallBinMin = Math.min(overallBinMin, min);
                overallBinMax = Math.max(overallBinMax, max);
            })
            // [overallBinMin, overallBinMax] = binsData.reduce(([minAcc, maxAcc], { min, max }) => 
            //     [Math.min(minAcc, min), Math.max(maxAcc, max)], 
            //     [Infinity, -Infinity]
            // );
            const subtitle = this.#getSubtitle([overallBinMin, overallBinMax]);
            d3.select(`#${subtitleDiv.id}`).html(subtitle);

            bounds.append("g")
                .attr("id", XAXIS_GROUP_ID)
                .attr("class", AXIS_CLASS_ID)
                .attr("transform", `translate(0,${dimensions.boundedHeight})`)
                .call(xAxis);
            
            this.state.data.overallBinMin = overallBinMin;
            this.state.data.overallBinMax = overallBinMax;  
            this.state.peripherals.axes.xAxis = xAxis;
            this.state.peripherals.axes.yAxis = yAxis;
            this.state.peripherals.header.title = title;
            this.state.peripherals.header.subtitle = subtitle;
            this.state.peripherals.header.titleDiv = titleDiv;
            this.state.peripherals.header.subtitleDiv = subtitleDiv;
        }
        
        #drawChart() {
            const { 
                BIN_RECT_CLASS_ID, XAXIS_GROUP_ID, YAXIS_GROUP_ID, 
                XAXIS_TICKS_NB, YAXIS_TICKS_NB 
            } = D3Histogram;
            const { dimensions, bounds, binDefaultFillColor } = this.state.chart;
            const binsData = Array.from(this.state.data.binsData.values());
    
            // Define accessors & scales
            const xAccessor = d => d.mean;
            const yAccessor = d => d.values.length;
            
            const xScale = d3.scaleBand()
                .domain(binsData.map(d => xAccessor(d)))
                .range([0, dimensions.boundedWidth])
                .padding(0.1);
    
            const yScale = d3.scaleLinear()
                .domain([0, d3.max(binsData, yAccessor)])
                .range([dimensions.boundedHeight, 0]);
    
            // Update bins
            const bins = bounds.selectAll(`.${BIN_RECT_CLASS_ID}`)
                .data(binsData, d => d.id);
    
            bins.enter()
                .append("rect")
                .attr("id", (_, i) => `${BIN_RECT_CLASS_ID}${i}`)
                .attr("class", BIN_RECT_CLASS_ID)
                .merge(bins)
                .attr("x", d => xScale(xAccessor(d)))
                .attr("y", d => yScale(yAccessor(d)))
                .attr("width", xScale.bandwidth())
                .attr("height", d => dimensions.boundedHeight - yScale(yAccessor(d)))
                .attr("fill", binDefaultFillColor);
    
            bins.exit().remove();

            this.state.peripherals.axes.originalXScaleRange = xScale.range();
            this.state.peripherals.axes.xAccessor = xAccessor;
            this.state.peripherals.axes.yAccessor = yAccessor;
            this.state.peripherals.axes.xScale = xScale;
            this.state.peripherals.axes.yScale = yScale;

            // Update axes
            this.#updateAxes(xScale, yScale, XAXIS_TICKS_NB, YAXIS_TICKS_NB);            
        }

        /**
         * Draws the chart.
         * 
         * @returns {undefined} No return value.
         * @private
         */    
        /*#drawChart() {
            const { 
                BIN_RECT_CLASS_ID, XAXIS_TICKS_NB, YAXIS_TICKS_NB 
            } = D3Histogram;
            const { dimensions, bounds, binDefaultFillColor } = this.state.chart;
            const binsData = Array.from(this.state.data.binsData.values());

            // Define accessors & scales
            const xAccessor = d => d.mean;
            const yAccessor = d => d.values.length;
            
            const xScale = d3.scaleBand()
                .domain(binsData.map(d => xAccessor(d)))
                .range([0, dimensions.boundedWidth])
                .padding(0.1);

            const yScale = d3.scaleLinear()
                .domain([0, d3.max(binsData, yAccessor)])
                .range([dimensions.boundedHeight, 0]);

            // Update bins
            const bins = bounds.selectAll(`.${BIN_RECT_CLASS_ID}`)
                .data(binsData, d => d.id);

            bins.enter()
                .append("rect")
                .attr("id", (_, i) => `${BIN_RECT_CLASS_ID}${i}`)
                .attr("class", BIN_RECT_CLASS_ID)
                .merge(bins)
                .attr("x", d => xScale(xAccessor(d)))
                .attr("y", d => yScale(yAccessor(d)))
                .attr("width", xScale.bandwidth())
                .attr("height", d => dimensions.boundedHeight - yScale(yAccessor(d)))
                .attr("fill", binDefaultFillColor);

            bins.exit().remove();

            // Update state
            this.state.peripherals.axes = {
                ...this.state.peripherals.axes,
                originalXScaleRange: xScale.range(),
                xAccessor,
                yAccessor,
                xScale,
                yScale
            };

            // Update axes
            this.#updateAxes(xScale, yScale, XAXIS_TICKS_NB, YAXIS_TICKS_NB);
        }*/

        /**
         * Updates the axes of the chart.
         * 
         * @param {d3.ScaleBand} xScale - The x-axis scale.
         * @param {d3.ScaleLinear} yScale - The y-axis scale.
         * @param {number} xTicksCount - The number of ticks for the x-axis.
         * @param {number} yTicksCount - The number of ticks for the y-axis.
         * @returns {undefined} No return value.
         * @private
         */
        /*#updateAxes(xScale, yScale, xTicksCount, yTicksCount) {
            const { XAXIS_GROUP_ID, YAXIS_GROUP_ID, AXIS_CLASS_ID } = D3Histogram;
            const { bounds, dimensions, chartContainerId } = this.state.chart;
            const { title } = this.state.peripherals.header;
            const binsData = this.state.data.binsData;

            // Y-axis
            const yAxisTickFormat = d3.format(".1s");
            const yAxis = d3.axisRight(yScale)
                .ticks(yTicksCount)
                .tickFormat(d => d === yScale.domain()[0] ? '' : yAxisTickFormat(d));

            let yAxisGroup = bounds.select(`#${YAXIS_GROUP_ID}`);
            if (yAxisGroup.empty()) {
                yAxisGroup = bounds.append("g")
                    .attr("id", YAXIS_GROUP_ID)
                    .attr("class", AXIS_CLASS_ID)
                    .style("transform", `translate(-${dimensions.margin.left * 0.5}px, 0px)`);
            }
            yAxisGroup.call(yAxis);

            // X-axis
            const xAxis = d3.axisBottom(xScale)
                .tickValues(this.#getAxisTickValues(xScale, xTicksCount))
                .tickFormat(d => this.#getFormattedAxisTickValue(d));

            let xAxisGroup = bounds.select(`#${XAXIS_GROUP_ID}`);
            if (xAxisGroup.empty()) {
                xAxisGroup = bounds.append("g")
                    .attr("id", XAXIS_GROUP_ID)
                    .attr("class", AXIS_CLASS_ID)
                    .attr("transform", `translate(0,${dimensions.boundedHeight})`);
            }
            xAxisGroup.call(xAxis);

            // Title & subtitle
            this.#updateTitleAndSubtitle(chartContainerId, title, binsData);

            // Update state
            this.state.peripherals.axes = {
                ...this.state.peripherals.axes,
                xAxis,
                yAxis
            };
        }*/

        /**
         * Updates the title and subtitle of the chart.
         * 
         * @param {string} chartContainerId - The ID of the chart container.
         * @param {string} title - The title of the chart.
         * @param {Map} binsData - The bins data.
         * @returns {undefined} No return value.
         * @private
         */
        /*#updateTitleAndSubtitle(chartContainerId, title, binsData) {
            const chartDiv = document.getElementById(chartContainerId);

            // Title
            let titleDiv = document.getElementById("d3histogram-title");
            if (!titleDiv) {
                titleDiv = document.createElement('div');
                titleDiv.id = "d3histogram-title";
                chartDiv.appendChild(titleDiv);
            }
            d3.select(`#${titleDiv.id}`).html(`<b>${title}</b>`);

            // Subtitle
            let subtitleDiv = document.getElementById("d3histogram-subtitle");
            if (!subtitleDiv) {
                subtitleDiv = document.createElement('div');
                subtitleDiv.id = "d3histogram-subtitle";
                chartDiv.appendChild(subtitleDiv);
            }

            const [overallBinMin, overallBinMax] = this.#getOverallBinRange(binsData);
            const subtitle = this.#getSubtitle([overallBinMin, overallBinMax]);
            d3.select(`#${subtitleDiv.id}`).html(subtitle);

            // Update state
            this.state.data.overallBinMin = overallBinMin;
            this.state.data.overallBinMax = overallBinMax;
            this.state.peripherals.header = {
                ...this.state.peripherals.header,
                title,
                subtitle,
                titleDiv,
                subtitleDiv
            };
        }*/

        /**
         * Calculates the overall bin range from the bins data.
         * 
         * @param {Map} binsData - The bins data.
         * @returns {Array} An array containing the minimum and maximum values.
         * @private
         */
        /*#getOverallBinRange(binsData) {
            let overallBinMin = Infinity;
            let overallBinMax = -Infinity;
            binsData.forEach(({ min, max }) => {
                overallBinMin = Math.min(overallBinMin, min);
                overallBinMax = Math.max(overallBinMax, max);
            });
            return [overallBinMin, overallBinMax];
        }*/   

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
            const binsFocusData = Array.from(this.state.data.binsFocusData.values());

            // Remove prior focus bins, if any
            bounds.select(`#${BIN_FOCUS_GROUP_ID}`).remove();

            // Draw focus bins
            // Update bins
            const binsFocusGroup = bounds.append("g").attr("id", BIN_FOCUS_GROUP_ID);
            const bins = binsFocusGroup.selectAll("g")
                .data(binsFocusData, d => d.id);
    
            bins.enter()
                .append("rect")
                .attr("id", (_, i) => `${BIN_FOCUS_RECT_CLASS_ID}${i}`)
                .attr("class", BIN_FOCUS_RECT_CLASS_ID)
                .merge(bins)
                .attr("x", d => xScale(xAccessor(d)))
                .attr("y", d => yScale(yAccessor(d)))
                .attr("width", xScale.bandwidth())
                .attr("height", d => dimensions.boundedHeight - yScale(yAccessor(d)))
                .attr("fill", binFocusDefaultFillColor)
                .attr("clip-path", `url(#${CLIP_BOUNDS_ID})`);
    
            bins.exit().remove();
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
         * @returns {undefined} No return value.
         * @private
         */
        #reset() {
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
                prevHoveredBinId 
            } = this.state.interactions;

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
            
            d3.select(`#${YAXIS_GROUP_ID}`).raise();
            d3.select(`#${INTERACTION_CONTAINER_ID}`).raise();

            this.state.interactions.isBrushingActive = isBrushingActive;
            this.state.interactions.prevBrushedDomain = prevBrushedDomain;
            this.state.interactions.prevHoveredBinId = prevHoveredBinId;
            this.state.interactions.isPanningActive = isPanningActive;
            this.state.interactions.prevPanX = prevPanX;    
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
                .on('mouseleave', e => this.#handleMouseLeave(e));

            // Set zoom behavior
            const maxK =  (binCount * BIN_MAX_WIDTH) / dimensions.boundedWidth;

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
            /*const brushedBins = data.reduce((brushedArr, d, _) => { 
                if(xAccessor(d) >= brushedDomain[0] && xAccessor(d) <= brushedDomain[1]) {
                    brushedArr.push(d);

                    brushedDomainBinned[0] = Math.min(brushedDomainBinned[0], d.min);
                    brushedDomainBinned[1] = Math.max(brushedDomainBinned[1], d.max);
                }
                return brushedArr;
            }, []);
            const brushedBinIds = brushedBins.map(b => b.id);*/
            let brushedBins = [];
            data.forEach((d, i) => {
                if(xAccessor(d) >= brushedDomain[0] && xAccessor(d) <= brushedDomain[1]) {
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
                ?  binFocusSelectedFillColor : binFocusUnselectedFillColor
            );

            // Update subtitle
            const subtitle = this.#getSubtitle(brushedDomainBinned);
            d3.select(`#${subtitleDiv.id}`).html(subtitle);

            // Update datamap plot
            const brushedIndices = brushedBins.map(d => d.indices).flat();
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
            const { isBrushingActive } = this.state.interactions;

            if (!isBrushingActive) { this.#reset(); }
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
            let { prevHoveredBinId } = this.state.interactions;

            // Locate hovered bin
            const data = this.#hasFocusChart() ? binsFocusData : binsData;
            const xCoord = d3.pointer(e)[0];

            /*const hoveredBinId = data.reduce((hoveredIs, d, i) => { 
                if (xCoord > xScale(xAccessor(d)) && xCoord <= xScale(xAccessor(d)) + xScale.bandwidth()) {
                    hoveredIs.push(i);
                }
                return hoveredIs;
            }, [])[0];*/
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
                .style("fill", (_, i) =>  i == hoveredBinId ? binFocusSelectedFillColor : binFocusUnselectedFillColor);

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
            let pannedRange = xScale.range().map(d => d+dX);

            if (pannedRange[1] < originalXScaleRange[1]) {
                pannedRange = [pannedRange[0] + originalXScaleRange[1] - pannedRange[1], originalXScaleRange[1]];
            } else if (pannedRange[0] > originalXScaleRange[0]) {
                pannedRange = [originalXScaleRange[0], pannedRange[1] - pannedRange[0] - originalXScaleRange[0]];
            }

           xScale.range(pannedRange);
           wrapper.select(`#${XAXIS_GROUP_ID}`).call(xAxis);

            // Update y-scale and y-axis
            const pannedDomain = originalXScaleRange.map(xScale.invert, xScale);
            const pannedBinsData = binsData.filter(d => xAccessor(d) >= pannedDomain[0] && xAccessor(d) <= pannedDomain[1]);

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
            if(isBrushingActive || e.sourceEvent.type !== "wheel" || prevZoomK == e.transform.k) return;
            prevZoomK = e.transform.k;
        
            // Update x-scale and x-axis
            xScale.range([0, dimensions.boundedWidth].map(d => e.transform.applyX(d)));
            
            xAxis.tickValues(this.#getAxisTickValues(xScale, XAXIS_TICKS_NB*e.transform.k));

            wrapper.select(`#${XAXIS_GROUP_ID}`)
                .transition()
                .call(xAxis);

            // Update y-scale and y-axis
            const zoomedDomain = originalXScaleRange.map(xScale.invert, xScale);
            const zoomedData = binsData.filter(d => xAccessor(d) >= zoomedDomain[0] && xAccessor(d) <= zoomedDomain[1]);

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
        /*#handleZoom(e) {
            const { isBrushingActive } = this.state.interactions;
            const { dimensions, bounds } = this.state.chart;
            const { binsData } = this.state.data;
            const { 
                XAXIS_GROUP_ID, YAXIS_GROUP_ID, XAXIS_TICKS_NB, 
                BIN_RECT_CLASS_ID, BIN_FOCUS_RECT_CLASS_ID 
            } = D3Histogram;
            const { 
                originalXScaleRange, xAccessor, yAccessor, 
                xScale, yScale
            } = this.state.peripherals.axes; 
            let { prevZoomK } = this.state.interactions;
    
            if (isBrushingActive || e.sourceEvent.type !== "wheel" || prevZoomK === e.transform.k) return;
            prevZoomK = e.transform.k;
        
            // Update x-scale
            xScale.range([0, dimensions.boundedWidth].map(d => e.transform.applyX(d)));
            
            // Update y-scale
            const zoomedDomain = originalXScaleRange.map(xScale.invert, xScale);
            const zoomedData = Array.from(binsData.values()).filter(d => 
                xAccessor(d) >= zoomedDomain[0] && xAccessor(d) <= zoomedDomain[1]
            );
            yScale.domain([0, d3.max(zoomedData, yAccessor)]);           
            
            // Update axes
            this.#updateAxes(xScale, yScale, XAXIS_TICKS_NB * e.transform.k, YAXIS_GROUP_ID);
    
            // Update bins
            this.#updateBins(xScale, yScale, dimensions.boundedHeight);
    
            this.state.interactions.prevZoomK = prevZoomK;
        }
        
        #updateBins(xScale, yScale, boundedHeight) {
            const { BIN_RECT_CLASS_ID, BIN_FOCUS_RECT_CLASS_ID } = D3Histogram;
            const { bounds } = this.state.chart;
            const { xAccessor, yAccessor } = this.state.peripherals.axes;
    
            bounds.selectAll(`.${BIN_RECT_CLASS_ID}, .${BIN_FOCUS_RECT_CLASS_ID}`)
                .transition()
                .attr("x", d => xScale(xAccessor(d)))
                .attr("y", d => yScale(yAccessor(d)))
                .attr("width", xScale.bandwidth())       
                .attr("height", d => boundedHeight - yScale(yAccessor(d)));
        }*/
 
        /**
         * Handles the zoom interaction on the chart. 
         * It updates the chart's scales, axes, and bins when a zoom event occurs. 
         * 
         * @param {Object} e - The zoom event object containing the transform information.
         * @returns {undefined} No return value.
         * @private
         */
        /*#handleZoom(e) {
            const { isBrushingActive } = this.state.interactions;
            const { dimensions } = this.state.chart;
            const { binsData } = this.state.data;
            const { XAXIS_TICKS_NB, YAXIS_TICKS_NB } = D3Histogram;
            const { 
                originalXScaleRange, xAccessor, yAccessor, 
                xScale, yScale
            } = this.state.peripherals.axes; 
            let { prevZoomK } = this.state.interactions;

            if (isBrushingActive || e.sourceEvent.type !== "wheel" || prevZoomK === e.transform.k) return;
            prevZoomK = e.transform.k;
        
            // Update x-scale
            const newXScale = xScale.copy()
                .range(originalXScaleRange.map(d => e.transform.applyX(d)));
            
            // Update y-scale
            const zoomedDomain = originalXScaleRange.map(newXScale.invert, newXScale);
            const zoomedData = Array.from(binsData.values()).filter(d => 
                xAccessor(d) >= zoomedDomain[0] && xAccessor(d) <= zoomedDomain[1]
            );
            const newYScale = yScale.copy()
                .domain([0, d3.max(zoomedData, yAccessor)]);           
            
            // Update axes and bins
            this.#updateAxes(newXScale, newYScale, XAXIS_TICKS_NB * e.transform.k, YAXIS_TICKS_NB);
            this.#updateBins(newXScale, newYScale);

            // Update state
            this.state.peripherals.axes.xScale = newXScale;
            this.state.peripherals.axes.yScale = newYScale;
            this.state.interactions.prevZoomK = prevZoomK;
        }*/

        /*
        #updateBins(xScale, yScale) {
            const { BIN_RECT_CLASS_ID, BIN_FOCUS_RECT_CLASS_ID } = D3Histogram;
            const { bounds, dimensions } = this.state.chart;
            const { xAccessor, yAccessor } = this.state.peripherals.axes;

            bounds.selectAll(`.${BIN_RECT_CLASS_ID}, .${BIN_FOCUS_RECT_CLASS_ID}`)
                .transition()
                .attr("x", d => xScale(xAccessor(d)))
                .attr("y", d => yScale(yAccessor(d)))
                .attr("width", xScale.bandwidth())       
                .attr("height", d => dimensions.boundedHeight - yScale(yAccessor(d)));
        }


        #getFormattedAxisTickValue(value) {
            const { dataType } = this.state.data;
            const { DATA_TYPE_E } = D3Histogram;

            switch (dataType) {
                case DATA_TYPE_E.NUMERICAL:
                    return d3.format(".2s")(value);
                case DATA_TYPE_E.TEMPORAL:
                    return d3.timeFormat("%b %Y")(value);
                case DATA_TYPE_E.CATEGORICAL:
                    return value;
                default:
                    return value;
            }
        }
        */
        
        #getAxisTickValues(scale, tickCount) {
            const domain = scale.domain();
            const step = Math.max(1, Math.floor(domain.length / tickCount));
            return domain.filter((_, i) => i % step === 0);
        }
//#endregion Interactions



        // **********************************************************************************
//#region  Peripherals
        // **********************************************************************************
        /*
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
        }*/

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
                return range[0] === range[1] ? `<b>${binsData[range[0]].label}</b>` : '';
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

            const tickBin = binsData.filter(b => xAccessor(b) === value)[0];
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