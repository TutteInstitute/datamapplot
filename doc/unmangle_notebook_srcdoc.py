import os
import glob
import html
import shutil

_ORIGINAL_NON_INLINE_WORKER = """
    const parsingWorkerBlob = new Blob([`
      self.onmessage = async function(event) {
        const { encodedData, JSONParse } = event.data;
        async function decompressFile(filename) {
          try {
            const response = await fetch(filename);
            if (!response.ok) {
              throw new Error(\`HTTP error! status: \${response.status}\`);
            }
            const reader = response.body
              .pipeThrough(new DecompressionStream("gzip"))
              .getReader();

            let chunks = [];
            let totalSize = 0;

            while (true) {
              const { done, value } = await reader.read();
              if (done) {
                break;
              }
              chunks.push(value);
              totalSize += value.length;
            }

            // Concatenate chunks into a single Uint8Array
            const decompressedData = new Uint8Array(totalSize);
            let position = 0;
            for (const chunk of chunks) {
              decompressedData.set(chunk, position);
              position += chunk.length;
            }

            return decompressedData;
          } catch (error) {
            console.error('Decompression failed:', error);
            throw error;
          }
        }
        const binaryData = await decompressFile(encodedData);
        if (JSONParse) {
          const parsedData = JSON.parse(new TextDecoder("utf-8").decode(binaryData));
          self.postMessage({ type: "data", data: parsedData });
        } else {
          // Send the parsed table back to the main thread
          self.postMessage({ type: "data", data: binaryData });
        }
      }
    `], { type: 'application/javascript' });
"""

_NOTEBOOK_NON_INLINE_WORKER = """
    const parsingWorkerBlob = new Blob([`
      async function DecompressBytes(bytes) {
          const blob = new Blob([bytes]);
          const decompressedStream = blob.stream().pipeThrough(
            new DecompressionStream("gzip")
          );
          const arr = await new Response(decompressedStream).arrayBuffer()
          return new Uint8Array(arr);
      }
      async function decodeBase64(base64) {
          return Uint8Array.from(atob(base64), c => c.charCodeAt(0));
      }
      async function decompressFile(filename) {
          const response = await fetch(filename, {
            headers: {Authorization: 'Token API_TOKEN'}
          });
          if (!response.ok) {
            throw new Error(\`HTTP error! status: \${response.status}\`);
          }
          const data = await response.json()
            .then(data => data.content)
            .then(base64data => decodeBase64(base64data))
            .then(buffer => DecompressBytes(buffer));
          return data;
      }
      self.onmessage = async function(event) {
        const { encodedData, JSONParse } = event.data;
        const binaryData = await decompressFile(encodedData);
        if (JSONParse) {
          const parsedData = JSON.parse(new TextDecoder("utf-8").decode(binaryData));
          self.postMessage({ data: parsedData });
        } else {
          // Send the parsed table back to the main thread
          self.postMessage({ data: binaryData });
        }
      }
    `], { type: 'application/javascript' });
"""

def unmangle_notebook_srcdoc(html_str, auto_example=False):
    new_html_str = html_str.replace(
        html.escape(_NOTEBOOK_NON_INLINE_WORKER), 
        html.escape(_ORIGINAL_NON_INLINE_WORKER),
    )
    return new_html_str

def process_html_files():
    print(f"Processing HTML files from {os.getcwd()}")
    for zipfile in glob.glob("examples/*gallery*.zip"):
        print(f"Moving {zipfile} to {os.environ['READTHEDOCS_OUTPUT'] + 'html/auto_examples/'}")
        shutil.copy(zipfile, os.environ['READTHEDOCS_OUTPUT'] + 'html/auto_examples/')
    for filename in glob.glob(os.environ["READTHEDOCS_OUTPUT"] + 'html/**/*.html', recursive=True):
        with open(filename, 'r') as f:
            html_str = f.read()
        if "srcdoc" in html_str and "headers: {Authorization:" in html_str:
            print(f"Patching {filename} srcdoc")
            new_html_str = unmangle_notebook_srcdoc(html_str)
            with open(filename, 'w') as f:
                f.write(new_html_str)

if __name__ == "__main__":
    process_html_files()