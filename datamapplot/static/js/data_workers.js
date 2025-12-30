/**
 * DataMapPlot Web Worker Code Templates
 * 
 * This module contains worker code templates for loading and decompressing data
 * in both inline and non-inline (file-based) modes.
 */

/**
 * Create inline data worker code with optional progress reporting.
 * @param {boolean} showProgress - Whether to report progress updates
 * @returns {string} - Worker code as a string
 */
function createInlineWorkerCode(showProgress = true) {
    const progressCode = showProgress ? `
        async function decodeBase64WithProgress(base64) {
            const totalLength = base64.length;
            const chunkSize = 1024 * 1024; // 1MB chunks
            let decodedArray = new Uint8Array(Math.ceil(totalLength * 3 / 4));
            let offset = 0;

            for (let i = 0; i < totalLength; i += chunkSize) {
                const chunk = base64.slice(i, i + chunkSize);
                const decodedChunk = Uint8Array.from(atob(chunk), c => c.charCodeAt(0));
                decodedArray.set(decodedChunk, offset);
                offset += decodedChunk.length;

                const progress = Math.min(100, Math.round((i + chunkSize) / totalLength * 100));
                self.postMessage({ type: 'progress', progress: progress });

                // Allow other operations to occur
                await new Promise(resolve => setTimeout(resolve, 0));
            }

            return decodedArray.slice(0, offset);
        }
    ` : `
        async function decodeBase64WithProgress(base64) {
            return Uint8Array.from(atob(base64), c => c.charCodeAt(0));
        }
    `;

    return `
        self.onmessage = async function(event) {
            const { encodedData, JSONParse } = event.data;
            
            async function DecompressBytes(bytes) {
                const blob = new Blob([bytes]);
                const decompressedStream = blob.stream().pipeThrough(
                    new DecompressionStream("gzip")
                );
                const arr = await new Response(decompressedStream).arrayBuffer();
                return new Uint8Array(arr);
            }
            ${progressCode}
            
            const decodedData = await decodeBase64WithProgress(encodedData);
            const decompressedData = await DecompressBytes(decodedData);
            
            if (JSONParse) {
                const parsedData = JSON.parse(new TextDecoder("utf-8").decode(decompressedData));
                self.postMessage({ type: "data", data: parsedData });
            } else {
                self.postMessage({ type: "data", data: decompressedData });
            }
        }
    `;
}

/**
 * Create non-inline (file-based) data worker code with optional progress reporting.
 * @param {boolean} showProgress - Whether to report progress updates
 * @returns {string} - Worker code as a string
 */
function createFileWorkerCode(showProgress = true) {
    return `
        self.onmessage = async function(event) {
            const { encodedData, JSONParse } = event.data;
            
            async function DecompressBytes(bytes) {
                const blob = new Blob([bytes]);
                const decompressedStream = blob.stream().pipeThrough(
                    new DecompressionStream("gzip")
                );
                const arr = await new Response(decompressedStream).arrayBuffer();
                return new Uint8Array(arr);
            }
            
            async function decompressFile(filename) {
                try {
                    // Get the current directory from the script location
                    const currentPath = self.location.href;
                    const directoryPath = currentPath.substring(0, currentPath.lastIndexOf('/') + 1);
                    const originURL = self.location.origin + directoryPath.replace(self.location.origin, '');
                    
                    const response = await fetch(originURL + filename);
                    if (!response.ok) {
                        throw new Error(\`HTTP error! status: \${response.status}. Failed to fetch: \${filename}\`);
                    }
                    const data = await response.arrayBuffer();
                    const decompressedData = await DecompressBytes(new Uint8Array(data));
                    return decompressedData;
                } catch (error) {
                    console.error('Decompression failed:', error);
                    throw error;
                }
            }
            
            let processedCount = 0;
            const decodedData = encodedData.map(async (file, i) => {
                const binaryData = await decompressFile(file);
                processedCount += 1;
                ${showProgress ? `self.postMessage({ type: "progress", progress: Math.round(((processedCount) / encodedData.length) * 95) });` : ''}
                
                if (JSONParse) {
                    const parsedData = JSON.parse(new TextDecoder("utf-8").decode(binaryData));
                    return { chunkIndex: i, chunkData: parsedData };
                } else {
                    return { chunkIndex: i, chunkData: binaryData };
                }
            });
            
            self.postMessage({ type: "data", data: await Promise.all(decodedData) });
        }
    `;
}

/**
 * Create Jupyter notebook compatible worker code for non-inline data.
 * This handles the special case where Jupyter API endpoints are needed.
 * @param {string|null} apiToken - Optional API token for authentication
 * @returns {string} - Worker code as a string
 */
function createJupyterWorkerCode(apiToken = null) {
    const authHeader = apiToken 
        ? `headers: {Authorization: 'Token ${apiToken}'}`
        : '';
    
    return `
        self.onmessage = async function(event) {
            const { encodedData, JSONParse } = event.data;
            
            async function DecompressBytes(bytes) {
                const blob = new Blob([bytes]);
                const decompressedStream = blob.stream().pipeThrough(
                    new DecompressionStream("gzip")
                );
                const arr = await new Response(decompressedStream).arrayBuffer();
                return new Uint8Array(arr);
            }
            
            async function decodeBase64(base64) {
                return Uint8Array.from(atob(base64), c => c.charCodeAt(0));
            }
            
            async function decompressFile(filename) {
                try {
                    const response = await fetch(filename, {
                        ${authHeader}
                    });
                    if (!response.ok) {
                        throw new Error(\`HTTP error! status: \${response.status}. Failed to fetch: \${filename}\`);
                    }
                    const decompressedData = await response.json()
                        .then(data => data.content)
                        .then(base64data => decodeBase64(base64data))
                        .then(buffer => DecompressBytes(buffer));
                    return decompressedData;
                } catch (error) {
                    console.error('Decompression failed:', error);
                    throw error;
                }
            }
            
            let processedCount = 0;
            const decodedData = encodedData.map(async (file, i) => {
                const binaryData = await decompressFile(file);
                processedCount += 1;
                self.postMessage({ type: "progress", progress: Math.round(((processedCount) / encodedData.length) * 95) });
                
                if (JSONParse) {
                    const parsedData = JSON.parse(new TextDecoder("utf-8").decode(binaryData));
                    return { chunkIndex: i, chunkData: parsedData };
                } else {
                    return { chunkIndex: i, chunkData: binaryData };
                }
            });
            
            self.postMessage({ type: "data", data: await Promise.all(decodedData) });
        }
    `;
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        createInlineWorkerCode,
        createFileWorkerCode,
        createJupyterWorkerCode
    };
}
