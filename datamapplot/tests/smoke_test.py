import base64
import gzip

import datamapplot
from datamapplot.widgets import ReembedWidget

# The re-embed engine (worker source and WASM) must ship with the package.
html = ReembedWidget().html
assert "wasm_bindgen" in html and "self.onmessage" in html
wasm = html.split('class="container-box reembed-container"', 1)[1]
wasm = wasm.split('type="application/octet-stream"', 1)[1].split(">", 1)[1].split("<", 1)[0]
assert gzip.decompress(base64.b64decode(wasm))[:4] == b"\0asm", "re-embed engine WASM missing"
