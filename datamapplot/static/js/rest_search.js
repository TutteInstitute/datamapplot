/**
 * RESTSearchWidget - Server-side search with configurable REST endpoint
 */
class RESTSearchWidget {
    constructor(containerId, config, datamap) {
        this.containerId = containerId;
        this.config = config;
        this.datamap = datamap;
        this.selectionManager = datamap.dataSelectionManager;
            
            // Debounce timer
            this.debounceTimer = null;
            
            // Current request controller for cancellation
            this.currentRequest = null;
            
            // Search state
            this.lastQuery = '';
            this.lastResults = [];
            
            this.initialize();
        }

        initialize() {
            const container = document.getElementById(this.containerId);
            if (!container) {
                console.error(`RESTSearchWidget: Container ${this.containerId} not found`);
                return;
            }

            this.render(container);
            this.attachEventListeners();
        }

        render(container) {
            container.innerHTML = `
                <div class="rest-search-widget">
                    <div class="rest-search-input-container">
                        <input 
                            type="text" 
                            class="rest-search-input" 
                            placeholder="${this.config.placeholder}"
                            autocomplete="off"
                        />
                        <div class="rest-search-loading" style="display: none;">
                            <div class="rest-search-spinner"></div>
                        </div>
                        <button class="rest-search-clear" style="display: none;" title="Clear search">
                            ×
                        </button>
                    </div>
                    ${this.config.show_result_count ? `
                        <div class="rest-search-results-info" style="display: none;">
                            <span class="rest-search-result-count"></span>
                        </div>
                    ` : ''}
                    <div class="rest-search-error" style="display: none;"></div>
                </div>
            `;
        }

        attachEventListeners() {
            const input = document.querySelector(`#${this.containerId} .rest-search-input`);
            const clearBtn = document.querySelector(`#${this.containerId} .rest-search-clear`);

            input.addEventListener('input', (e) => this.handleInput(e.target.value));
            clearBtn.addEventListener('click', () => this.clearSearch());
            
            // Enter key triggers immediate search (bypass debounce)
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    clearTimeout(this.debounceTimer);
                    this.performSearch(e.target.value);
                }
            });
        }

        handleInput(query) {
            // Clear previous timer
            clearTimeout(this.debounceTimer);
            
            // Show/hide clear button
            const clearBtn = document.querySelector(`#${this.containerId} .rest-search-clear`);
            clearBtn.style.display = query.length > 0 ? 'block' : 'none';

            // Clear search if query is empty
            if (query.length === 0) {
                this.clearResults();
                return;
            }

            // Check minimum length
            if (query.length < this.config.min_query_length) {
                this.hideLoading();
                this.hideError();
                return;
            }

            // Debounce the search
            this.debounceTimer = setTimeout(() => {
                this.performSearch(query);
            }, this.config.debounce_ms);
        }

        async performSearch(query) {
            // Cancel previous request if still pending
            if (this.currentRequest) {
                this.currentRequest.abort();
            }

            this.lastQuery = query;
            this.showLoading();
            this.hideError();

            try {
                // Create abort controller for this request
                this.currentRequest = new AbortController();
                
                // Build request
                const requestOptions = this.buildRequest(query);
                requestOptions.signal = this.currentRequest.signal;

                // Set timeout
                const timeoutId = setTimeout(() => {
                    this.currentRequest.abort();
                }, this.config.timeout_ms);

                // Perform fetch
                const response = await fetch(this.config.endpoint_url, requestOptions);
                clearTimeout(timeoutId);

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }

                const data = await response.json();
                
                // Extract results using response_path
                const results = this.extractResults(data);
                
                this.handleResults(results);

            } catch (error) {
                if (error.name === 'AbortError') {
                    console.log('Search request cancelled');
                } else {
                    this.handleError(error);
                }
            } finally {
                this.hideLoading();
                this.currentRequest = null;
            }
        }

        buildRequest(query) {
            const options = {
                method: this.config.http_method,
                headers: {
                    'Content-Type': 'application/json',
                    ...this.config.auth_headers
                }
            };

            if (this.config.http_method === 'POST') {
                // Replace {query} placeholder in request body template
                const body = JSON.parse(
                    JSON.stringify(this.config.request_body_template)
                        .replace(/\{query\}/g, query)
                );
                options.body = JSON.stringify(body);
            } else {
                // For GET, append query as URL parameter
                const url = new URL(this.config.endpoint_url);
                url.searchParams.append('query', query);
                options.url = url.toString();
            }

            return options;
        }

        extractResults(data) {
            // Navigate through response_path to find results array
            const path = this.config.response_path.split('.');
            let current = data;
            
            for (const key of path) {
                if (current && typeof current === 'object' && key in current) {
                    current = current[key];
                } else {
                    console.warn(`Response path "${this.config.response_path}" not found in response`);
                    return [];
                }
            }

            if (!Array.isArray(current)) {
                console.warn(`Response path "${this.config.response_path}" did not resolve to an array`);
                return [];
            }

            return current;
        }

        handleResults(results) {
            this.lastResults = results;

            // Extract point IDs from results
            const pointIds = results
                .map(result => result[this.config.id_field])
                .filter(id => id !== undefined && id !== null);

            if (pointIds.length === 0) {
                this.showError('No results found');
                this.updateResultCount(0);
                this.selectionManager.clearSelection();
                return;
            }

            // Update result count display
            this.updateResultCount(pointIds.length);

            // Apply selection to datamap
            // Use replace mode to show only search results
            this.selectionManager.setSelectionMode('replace');
            this.selectionManager.selectByIds(pointIds);
        }

        handleError(error) {
            console.error('REST Search error:', error);
            this.showError(`Search failed: ${error.message}`);
            this.updateResultCount(0);
        }

        clearSearch() {
            const input = document.querySelector(`#${this.containerId} .rest-search-input`);
            input.value = '';
            this.clearResults();
            
            const clearBtn = document.querySelector(`#${this.containerId} .rest-search-clear`);
            clearBtn.style.display = 'none';
        }

        clearResults() {
            this.lastQuery = '';
            this.lastResults = [];
            this.hideError();
            this.hideLoading();
            this.updateResultCount(0);
            this.selectionManager.clearSelection();
        }

        showLoading() {
            const loading = document.querySelector(`#${this.containerId} .rest-search-loading`);
            if (loading) loading.style.display = 'block';
        }

        hideLoading() {
            const loading = document.querySelector(`#${this.containerId} .rest-search-loading`);
            if (loading) loading.style.display = 'none';
        }

        showError(message) {
            const errorDiv = document.querySelector(`#${this.containerId} .rest-search-error`);
            if (errorDiv) {
                errorDiv.textContent = message;
                errorDiv.style.display = 'block';
            }
        }

        hideError() {
            const errorDiv = document.querySelector(`#${this.containerId} .rest-search-error`);
            if (errorDiv) {
                errorDiv.style.display = 'none';
            }
        }

        updateResultCount(count) {
            if (!this.config.show_result_count) return;
            
            const countSpan = document.querySelector(`#${this.containerId} .rest-search-result-count`);
            const infoDiv = document.querySelector(`#${this.containerId} .rest-search-results-info`);
            
            if (countSpan && infoDiv) {
                if (count > 0) {
                    countSpan.textContent = `${count} result${count !== 1 ? 's' : ''} found`;
                    infoDiv.style.display = 'block';
                } else if (this.lastQuery.length >= this.config.min_query_length) {
                    countSpan.textContent = 'No results found';
                    infoDiv.style.display = 'block';
                } else {
                    infoDiv.style.display = 'none';
                }
            }
        }
    }
}
