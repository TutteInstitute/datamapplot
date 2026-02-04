from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
import string

from datamapplot.config import ConfigManager


cfg = ConfigManager()

_DEFAULT_TAG_COLORS = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
    "#a6008a",
    "#656100",
    "#8aa6ff",
    "#007155",
    "#ce968a",
    "#6139f3",
    "#82b692",
    "#ae8210",
    "#ae9ebe",
    "#5d5d79",
    "#ce86ff",
    "#398e92",
    "#b65504",
    "#ce31d7",
    "#758a55",
    "#9204c6",
    "#187100",
    "#965982",
    "#ef6959",
    "#5d79ff",
    "#7986b2",
    "#b2a66d",
    "#5d614d",
    "#009e71",
    "#00a2e7",
    "#8ea6ae",
    "#8a9a0c",
    "#9e7d5d",
    "#00c66d",
    "#246979",
    "#65c210",
    "#865510",
    "#a23118",
    "#9e7dff",
    "#9239fb",
    "#00c2a6",
    "#ae7d9e",
    "#6165b2",
    "#aaa69e",
    "#005def",
    "#754d8e",
    "#ce7d49",
    "#ba5549",
    "#f35dff",
    "#df9600",
    "#be4dff",
    "#55716d",
    "#8ab65d",
    "#6d9686",
    "#e75500",
    "#75616d",
    "#4d713d",
    "#5d8200",
    "#9e45a6",
    "#7daed7",
    "#867596",
    "#5d798e",
    "#ba75c6",
    "#be55a2",
    "#827135",
    "#008641",
    "#5d96b2",
    "#ae9ae7",
    "#61a261",
    "#b6756d",
    "#5daaa6",
    "#eb41c6",
    "#8e9e7d",
    "#9e8e96",
    "#b69e10",
    "#6d49b6",
    "#867d00",
    "#a66d2d",
    "#ca92c6",
    "#6592df",
    "#4d8265",
    "#7d6d5d",
    "#7d65ef",
    "#45658a",
    "#8a8e9e",
    "#d29a55",
    "#b220df",
    "#9a8e4d",
    "#0086eb",
    "#00829e",
    "#969eca",
    "#c614aa",
    "#007975",
    "#9a86be",
    "#5d6165",
    "#c67100",
    "#755939",
    "#9a4d24",
    "#8e3d7d",
    "#c23900",
    "#6d7961",
    "#eb8a69",
    "#35baeb",
    "#b29679",
    "#718a8e",
    "#9e69a2",
    "#ae75e3",
    "#008a00",
    "#3561ae",
    "#8e9692",
    "#a66549",
    "#7d82db",
    "#00a2b6",
    "#24b682",
    "#9e00aa",
    "#08ba39",
    "#8a49ba",
    "#75659e",
    "#008e79",
    "#5579c6",
    "#927186",
    "#558a41",
    "#755171",
]


class SelectionHandlerBase:
    """Base class for selection handlers. Selection handlers are used to define custom behavior
    when text items are selected on the plot. This can include displaying additional information
    about the selected text items, generating visualizations based on the selected text items, or
    interacting with external APIs to process the selected text items.

    Parameters
    ----------
    location : str, optional
        The location for the handler's display element. Should be one of:
        "top-left", "top-right", "bottom-left", "bottom-right",
        "left-drawer", "right-drawer", "bottom-drawer".
        Default is None.

    order : int, optional
        The stacking order within the location (0-100, lower values appear first).
        Default is 50.

    dependencies : list, optional
        A list of URLs for external dependencies required by the selection handler. Default is an empty list.

    """

    def __init__(self, location=None, order=50, **kwargs):
        self.location = location
        self.order = order if order is not None else 50
        if "dependencies" in kwargs:
            self.dependencies = kwargs["dependencies"]
        else:
            self.dependencies = []

    @property
    def javascript(self):
        return ""

    @property
    def css(self):
        return ""

    @property
    def html(self):
        return ""


class DisplaySample(SelectionHandlerBase):
    """A selection handler that displays a sample of the selected text items in a container on the page.
    The sample will be randomly selected from the full selection of text items, and the number of samples
    can be controlled by the `n_samples` parameter.

    A resample button is also provided to generate a new sample of text items from the selection.

    Parameters
    ----------
    n_samples : int, optional
        The number of samples to display. Default is 256.

    font_family : str, optional
        The font family to use for the displayed text. Default is None.

    **kwargs
        Additional keyword arguments to pass to the SelectionHandlerBase constructor.

    """

    @cfg.complete(unconfigurable={"self", "n_samples"})
    def __init__(
        self,
        n_samples=256,
        font_family=None,
        location="right-drawer",
        order=10,
        cdn_url="unpkg.com",
        other_triggers=None,
        **kwargs,
    ):
        super().__init__(
            location=location,
            order=order,
            dependencies=[f"https://{cdn_url}/jquery@3.7.1/dist/jquery.min.js"],
            **kwargs,
        )
        self.n_samples = n_samples
        self.font_family = font_family
        self.other_triggers = other_triggers

    @property
    def javascript(self):
        result = f"""
// Find or create container in stack
function findStackContainer(location) {{
    let stack = document.getElementsByClassName("stack " + location)[0];
    if (!stack && location.includes("drawer")) {{
        // Extract drawer direction (e.g., "right" from "right-drawer")
        const drawerDirection = location.replace("-drawer", "");
        const drawer = document.querySelector(".drawer-container.drawer-" + drawerDirection);
        if (drawer) {{
            stack = drawer;
        }}
    }}
    return stack;
}}

function ensureSelectionContainer() {{
    let selectionContainer = document.getElementById("selection-container");
    
    if (!selectionContainer) {{
        const stackContainer = findStackContainer("{self.location}");
        if (!stackContainer) {{
            console.warn("Stack container for {self.location} not found yet");
            return null;
        }}
        
        selectionContainer = document.createElement("div");
        selectionContainer.id = "selection-container";
        selectionContainer.className = "container-box more-opaque stack-box";
        selectionContainer.style.display = "none";
        selectionContainer.dataset.order = "{self.order}";
        
        // Create buttons and display div
        const resampleButton = document.createElement("button");
        resampleButton.className = "button resample-button";
        resampleButton.textContent = "Resample";
        resampleButton.onclick = resampleSelection;
        
        const clearSelectionButton = document.createElement("button");
        clearSelectionButton.className = "button clear-selection-button";
        clearSelectionButton.onclick = clearSelection;
        
        const selectionDisplayDiv = document.createElement("div");
        selectionDisplayDiv.id = "selection-display";
        
        selectionContainer.appendChild(resampleButton);
        selectionContainer.appendChild(clearSelectionButton);
        selectionContainer.appendChild(selectionDisplayDiv);
        
        stackContainer.appendChild(selectionContainer);
    }}
    
    return selectionContainer;
}}

// Ensure container exists (will be created on first selection if not ready now)
ensureSelectionContainer();

const shuffle = ([...arr]) => {{
  let m = arr.length;
  while (m) {{
    const i = Math.floor(Math.random() * m--);
    [arr[m], arr[i]] = [arr[i], arr[m]];
  }}
  return arr;
}};
const sampleSize = ([...arr], n = 1) => shuffle(arr).slice(0, n);

function samplerCallback(selectedPoints) {{
    const n_samples = {self.n_samples};
    const selectionContainer = ensureSelectionContainer();
    
    if (!selectionContainer) {{
        console.warn("Selection container not available yet");
        return;
    }}
    
    if (selectedPoints.length == 0) {{
        selectionContainer.style.display = 'none';
        return;       
    }}
    
    if (selectedPoints.length > n_samples) {{
        selectedPoints = sampleSize(selectedPoints, n_samples);
    }}
    
    const selectionDisplayDiv = document.getElementById('selection-display');
    var listItems = document.createElement('ul');
    while (selectionDisplayDiv.firstChild) {{
        selectionDisplayDiv.removeChild(selectionDisplayDiv.firstChild);
    }}
    if (datamap.metaData) {{
      selectedPoints.forEach((index) => {{
          listItems.appendChild(document.createElement('li')).textContent = datamap.metaData.hover_text[index];
      }});
    }} else {{
        listItems.appendChild(document.createElement('li')).textContent = "Meta data still loading ..."
    }}
    selectionDisplayDiv.appendChild(listItems);
    selectionContainer.style.display = 'block';
    
    // Open drawer if in drawer location
    if ("{self.location}".includes("drawer") && window.drawerManager) {{
        const drawerDirection = "{self.location}".replace("-drawer", "");
        window.drawerManager.openDrawer(drawerDirection);
    }}
}}

function resampleSelection() {{
    const n_samples = {self.n_samples};
    let selectedPoints = Array.from(datamap.getSelectedIndices());
    if (selectedPoints.length > n_samples) {{
        selectedPoints = sampleSize(selectedPoints, n_samples);
    }}
    const selectionContainer = ensureSelectionContainer();
    if (!selectionContainer) return;
    
    const selectionDisplayDiv = document.getElementById('selection-display');
    var listItems = document.createElement('ul');
    while (selectionDisplayDiv.firstChild) {{
        selectionDisplayDiv.removeChild(selectionDisplayDiv.firstChild);
    }}
    if (datamap.metaData) {{
      selectedPoints.forEach((index) => {{
          listItems.appendChild(document.createElement('li')).textContent = datamap.metaData.hover_text[index];
      }});
    }} else {{
        listItems.appendChild(document.createElement('li')).textContent = "Meta data still loading ..."
    }}
    selectionDisplayDiv.appendChild(listItems);
}}

function clearSelection() {{
    const selectionContainer = ensureSelectionContainer();
    if (!selectionContainer) return;
    
    selectionContainer.style.display = 'none';
    
    // Close drawer if in drawer location
    if ("{self.location}".includes("drawer") && window.drawerManager) {{
        const drawerDirection = "{self.location}".replace("-drawer", "");
        window.drawerManager.closeDrawer(drawerDirection);
    }}

    datamap.removeSelection(datamap.lassoSelectionItemId);
}}

await datamap.addSelectionHandler(samplerCallback);
        """
        if self.other_triggers:
            for trigger in self.other_triggers:
                result += f"""await datamap.addSelectionHandler(samplerCallback, "{trigger}");\n"""
        return result

    @property
    def css(self):
        if self.font_family:
            font_family_str = f"font-family: {self.font_family};"
        else:
            font_family_str = ""
        return f"""
    #selection-container {{
        display: none;
        {font_family_str}
    }}
    #selection-display {{
        overflow-y: auto;
        max-height: 80vh;
        margin: 8px;
    }}
    .button {{
        border: none;
        padding: 12px 24px;
        text-align: center;
        display: inline-block;
        margin: 4px 2px;
        cursor: pointer;
        border-radius: 8px;
    }}
    .resample-button {{
        background-color: #4CAF50;
        color: white;
    }}
    .clear-selection-button {{
        position: absolute;
        top: 0;
        right: 0;
        margin: 16px 14px;
        padding: 4px 8px;
        background-color: #b42316;
        color: white;
    }}
    .clear-selection-button:after {{
        font-size: 20px;
        content: "×";
    }}
        """

    @property
    def html(self):
        return ""  # Container created dynamically in JavaScript


class WordCloud(SelectionHandlerBase):
    """A selection handler that generates a word cloud from the selected text items. The word cloud
    is displayed in a container on the page, and the number of words in the cloud can be controlled
    by the `n_words` parameter.

    The word cloud is generated using the d3-cloud library, and the appearance of the word cloud can
    be customized using the `width`, `height`, `font_family`, `stop_words`, `n_rotations`, and `color_scale`
    parameters.

    Parameters
    ----------
    n_words : int, optional
        The number of words to display in the word cloud. Default is 256.

    width : int, optional
        The width of the word cloud container. Default is 500.

    height : int, optional
        The height of the word cloud container. Default is 500.

    font_family : str, optional
        The font family to use for the word cloud. Default is None.

    stop_words : list, optional
        A list of stop words to exclude from the word cloud. Default is the English stop words from scikit-learn.

    n_rotations : int, optional
        The number of rotations to use for the words in the word cloud. Default is 0. More rotations can make the
        word cloud more visually interesting, at the cost of readability.

    color_scale : str, optional
        The color scale to use for the word cloud. Default is "YlGnBu". The color scale can be any d3 color scale
        name, with an optional "_r" suffix to reverse the color scale.

    location : str, optional
        The location of the word cloud container on the page. Default is "bottom-right".
        Should be one of "top-left", "top-right", "bottom-left", or "bottom-right".

    **kwargs
        Additional keyword arguments to pass to the SelectionHandlerBase constructor.

    """

    @cfg.complete(unconfigurable={"self", "width", "height", "n_words"})
    def __init__(
        self,
        n_words=256,
        width=500,
        height=500,
        font_family=None,
        stop_words=None,
        n_rotations=0,
        use_idf=False,
        color_scale="YlGnBu",
        location="bottom-right",
        order=50,
        cdn_url="unpkg.com",
        other_triggers=None,
        **kwargs,
    ):
        super().__init__(
            location=location,
            order=order,
            dependencies=[
                f"https://{cdn_url}/d3@latest/dist/d3.min.js",
                f"https://{cdn_url}/d3-cloud@1.2.7/build/d3.layout.cloud.js",
                f"https://{cdn_url}/jquery@3.7.1/dist/jquery.min.js",
            ],
            **kwargs,
        )
        self.n_words = n_words
        self.width = width
        self.height = height
        self.font_family = font_family
        self.stop_words = stop_words or list(ENGLISH_STOP_WORDS)
        self.n_rotations = min(22, n_rotations)
        self.use_idf = str(use_idf).lower()
        if color_scale.endswith("_r"):
            self.color_scale = string.capwords(color_scale[:1]) + color_scale[1:-2]
            self.color_scale_reversed = True
        else:
            self.color_scale = string.capwords(color_scale[:1]) + color_scale[1:]
            self.color_scale_reversed = False
        self.other_triggers = other_triggers

    @property
    def javascript(self):
        result = f"""
const _STOPWORDS = new Set({self.stop_words});
const _ROTATIONS = [0, -90, 90, -45, 45, -30, 30, -60, 60, -15, 15, -75, 75, -7.5, 7.5, -22.5, 22.5, -52.5, 52.5, -37.5, 37.5, -67.5, 67.5];
let wordCloudStackContainer = document.getElementsByClassName("stack {self.location}")[0];
const wordCloudItem = document.createElement("div");
wordCloudItem.id = "word-cloud";
wordCloudItem.className = "container-box more-opaque stack-box";
wordCloudItem.dataset.order = "{self.order}";
wordCloudStackContainer.appendChild(wordCloudItem);

const wordCloudSvg = d3.select("#word-cloud").append("svg")
    .attr("width", {self.width})
    .attr("height", {self.height})
    .append("g")
    .attr("transform", "translate(" + {self.width} / 2 + "," + {self.height} / 2 + ")");

var wordCounter = null;
if ({self.use_idf}) {{
    while (!datamap.metaData) {{
        await new Promise(resolve => setTimeout(resolve, 100));
    }}
    const globalIDF = new Map();
    const globalDocFreq = new Map();
    const globalTotalDocs = datamap.metaData.hover_text.length;

    // Compute global IDF scores
    datamap.metaData.hover_text.forEach(text => {{
        const uniqueWords = new Set(
            text.toLowerCase()
                .split(/\\s+/)
                .filter(word => !_STOPWORDS.has(word))
        );
        uniqueWords.forEach(word => {{
            globalDocFreq.set(word, (globalDocFreq.get(word) || 0) + 1);
        }});
    }});
    globalDocFreq.forEach((freq, word) => {{
        globalIDF.set(word, Math.log(globalTotalDocs / (0.5 + freq)));
    }});

    wordCounter = function (textItems) {{
        const tfIdfScores = new Map();
        const words = textItems.join(' ')
            .toLowerCase()
            .split(/\\s+/)
            .filter(word => !_STOPWORDS.has(word));
        
        // Calculate term frequencies
        words.forEach(word => {{
            tfIdfScores.set(word, (tfIdfScores.get(word) || 0) + 1);
        }});
        
        // Convert raw counts to TF-IDF scores
        const result = Array.from(tfIdfScores, ([word, tf]) => ({{
            text: word,
            size: Math.sqrt(tf) * (globalIDF.get(word) || 0)
        }}))
        .sort((a, b) => b.size - a.size)
        .slice(0, {self.n_words}); 
        
        // Normalize scores to [0,1] range
        const maxSize = Math.max(...result.map(x => x.size));
        return result.map(({{text, size}}) => ({{
            text,
            size: size / maxSize
        }}));
    }}
}} else {{
    wordCounter = function (textItems) {{
        const words = textItems.join(' ').toLowerCase().split(/\\s+/);
        const wordCounts = new Map();
        words.forEach(word => {{
            wordCounts.set(word, (wordCounts.get(word) || 0) + 1);
        }});
        _STOPWORDS.forEach(stopword => wordCounts.delete(stopword));
        const result = Array.from(wordCounts, ([word, frequency]) => ({{ text: word, size: Math.sqrt(frequency) }}))
                            .sort((a, b) => b.size - a.size).slice(0, {self.n_words});
        const maxSize = Math.max(...(result.map(x => x.size)));
        return result.map(({{text, size}}) => ({{ text: text, size: (size / maxSize)}}));
    }}
}}

function generateWordCloud(words) {{
  const width = {self.width};
  const height = {self.height};

  const colorScale = d3.scaleSequential(d3.interpolate{self.color_scale}).domain([{"width / 10, 0" if self.color_scale_reversed else "0, width / 10"}]);

  // Configure a cloud layout
  const layout = d3.layout.cloud()
    .size([width, height])
    .words(words.map(d => ({{text: d.text, size: d.size * width / 10}})))
    .padding(1)
    .rotate(() => _ROTATIONS[~~(Math.random() * {self.n_rotations})])
    .font("{self.font_family or 'Impact'}")
    .fontSize(d => d.size)
    .fontWeight(d => Math.max(300, Math.min(d.size * 9000 / width, 900)))
    .on("end", draw);

  layout.start();

  function draw(words) {{
    const t = d3.transition().duration(300);
    
    // Update existing words
    const text = wordCloudSvg.selectAll("text")
      .data(words, d => d.text);
    
    // Remove old words
    text.exit()
      .transition(t)
      .attr("fill-opacity", 0)
      .attr("font-size", 1)
      .remove();
    // Add new words
    text.enter()
      .append("text")
      .attr("text-anchor", "middle")
      .attr("fill-opacity", 0)
      .attr("font-size", 1)
      .attr("font-family", "{self.font_family or 'Impact'}")
      .text(d => d.text)
      .merge(text) // Merge enter and update selections
      .transition(t)
      .attr("transform", d => "translate(" + [d.x, d.y] + ")rotate(" + d.rotate + ")")
      .attr("fill-opacity", 1)
      .attr("font-size", d => d.size)
      .attr("font-weight", d => Math.max(300, Math.min(d.size * 9000 / width, 900)))
      .attr("fill", d => colorScale(d.size));
  }}
}}

const shuffle = ([...arr]) => {{
  let m = arr.length;
  while (m) {{
    const i = Math.floor(Math.random() * m--);
    [arr[m], arr[i]] = [arr[i], arr[m]];
  }}
  return arr;
}};
const sampleSize = ([...arr], n = 1) => shuffle(arr).slice(0, n);

function wordCloudCallback(selectedPoints) {{
    if (selectedPoints.length > 0) {{
        $(wordCloudItem).animate({{height:'show'}}, 250);
    }} else {{
        $(wordCloudItem).animate({{height:'hide'}}, 250);
    }}
    let selectedText;
    if (datamap.metaData) {{
        selectedText = sampleSize(selectedPoints, 10000).map(i => datamap.metaData.hover_text[i]);
    }} else {{
        selectedText = ["Meta data still loading ..."];
    }}
    const wordCounts = wordCounter(selectedText);
    generateWordCloud(wordCounts);
}}

await datamap.addSelectionHandler(debounce(wordCloudCallback, 100));
"""
        if self.other_triggers:
            for trigger in self.other_triggers:
                result += f"""await datamap.addSelectionHandler(debounce(wordCloudCallback, 100), "{trigger}");\n"""
        return result

    @property
    def html(self):
        # return """<div id="word-cloud" class="container-box more-opaque"></div>"""
        return ""

    @property
    def css(self):
        return f"""
#word-cloud {{
    position: relative;
    display: none;
    width: {self.width}px;
    height: {self.height}px;
    z-index: 10;
}}
"""


class CohereSummary(SelectionHandlerBase):
    """A selection handler that uses the Cohere API to generate a summary of selected text items.
    The handler requires an API key to be provided by the end-user in the resulting HTML page.
    The handler will generate a prompt based on the selected text items and keywords extracted
    from the text items, and get a Cohere model to summarize this. The summary will be displayed
    in a container on the page.

    This handler can likely be adapted to other API services that provide text summarization.

    Note that the API key handling here is secure enough for private or small-scale use,
    but is not suitable for enterprise or production use.

    Parameters
    ----------
    model : str, optional
        The Cohere model to use for summarization. Default is "command-r". See the Cohere docs
        for more information on available models.

    stop_words : list, optional
        A list of stop words to exclude from the keyword extraction. Default is the English stop
        words from scikit-learn.

    n_keywords : int, optional
        The number of keywords to extract from the text items. Default is 128.

    n_samples : int, optional
        The number of samples to use for the summary. Default is 64.

    width : int, optional
        The width of the summary container. Default is 500.

    location : str, optional
        The location of the summary container on the page. Default is "top-right".
        Should be one of "top-left", "top-right", "bottom-left", or "bottom-right".

    **kwargs
        Additional keyword arguments to pass to the SelectionHandlerBase constructor.
    """

    @cfg.complete(unconfigurable={"self", "width", "n_keywords", "n_samples"})
    def __init__(
        self,
        model="command-r",
        stop_words=None,
        n_keywords=128,
        n_samples=64,
        width=500,
        location="top-right",
        order=50,
        cdn_url="unpkg.com",
        other_triggers=None,
        **kwargs,
    ):
        super().__init__(
            location=location,
            order=order,
            dependencies=[
                f"https://{cdn_url}/jquery@3.7.1/dist/jquery.min.js",
            ],
            **kwargs,
        )
        self.model = model
        self.stop_words = stop_words or list(ENGLISH_STOP_WORDS)
        self.n_keywords = n_keywords
        self.n_samples = n_samples
        self.width = width
        self.other_triggers = other_triggers

    @property
    def javascript(self):
        result = f"""
// Stop word list
const _STOPWORDS = new Set({self.stop_words});
const cohereStackContainer = document.getElementsByClassName("stack {self.location}")[0];
const summaryLayout = document.createElement("div");
summaryLayout.id = "layout-container";
summaryLayout.dataset.order = "{self.order}";
const apiContainer = document.createElement("div");
apiContainer.id = "api-key-container";
apiContainer.className = "container-box more-opaque stack-box";
const keyLabel = document.createElement("label");
keyLabel.for = "apiKey";
keyLabel.textContent = "Cohere API Key: ";
const keyInput = document.createElement("input");
keyInput.autocomplete = "off";
keyInput.type = "password";
keyInput.id - "api-key";
keyInput.placeholder = "Enter your API key here";
apiContainer.appendChild(keyLabel);
apiContainer.appendChild(keyInput);
summaryLayout.appendChild(apiContainer);
const summaryContainer = document.createElement("div");
summaryContainer.id = "summary-container";
summaryContainer.className = "container-box more-opaque";
summaryLayout.appendChild(summaryContainer);
cohereStackContainer.appendChild(summaryLayout);

// Cohere API call
async function cohereChat(message, apiKey) {{
  const response = await fetch('https://api.cohere.ai/v1/chat', {{
    method: 'POST',
    headers: {{
      'Authorization': `Bearer ${{apiKey}}`,
      'Content-Type': 'application/json'
    }},
    body: JSON.stringify({{
      message: message,
      model: "{self.model}"
    }})
  }});
  if (!response.ok) {{
    if (response.status === 401) {{
        return {{ text: "Error! Unauthorized: Please check your API key." }};
    }} else {{
        return {{ text: `Error! status: ${{response.status}}` }};
    }}
  }}
  return await response.json();
}}

// Word counts for keywords
function wordCounter(textItems) {{
    const words = textItems.join(' ').toLowerCase().split(/\\s+/);
    const wordCounts = new Map();
    words.forEach(word => {{
        wordCounts.set(word, (wordCounts.get(word) || 0) + 1);
    }});
    _STOPWORDS.forEach(stopword => wordCounts.delete(stopword));
    const result = Array.from(wordCounts, ([word, frequency]) => ({{ text: word, size: Math.sqrt(frequency) }}))
                        .sort((a, b) => b.size - a.size).slice(0, {self.n_keywords});
    const maxSize = Math.max(...(result.map(x => x.size)));
    return result.map(({{text, size}}) => ({{ text: text, size: (size / maxSize)}}));
}}

// Array shuffling for random sampling
const shuffle = ([...arr]) => {{
  let m = arr.length;
  while (m) {{
    const i = Math.floor(Math.random() * m--);
    [arr[m], arr[i]] = [arr[i], arr[m]];
  }}
  return arr;
}};
const sampleSize = ([...arr], n = 1) => shuffle(arr).slice(0, n);

// Create a summary using Cohere API
function generateSummary(textItems) {{
    const apiKey = document.getElementById("api-key").value;
    if (apiKey === "") {{
      summaryContainer.innerHTML = "No API Key provided ... cannot generate a summary!"
    }} else {{
        const keywords = wordCounter(textItems).map(d => d.text);
        const sample_text = sampleSize(textItems, {self.n_samples});

        // Build prompt from keywords and samples with some framing text
        const prompt = `We have samples of items from a selection of items about a topic.
Keywords associated to the topic are: ${{keywords.join(", ")}}
Samples text items associated to the topic are: 
- ${{sample_text.join("\\n  - ")}}

Please provide a concise summary of the selection of items. Be as specific as possible.
The summary should be a few sentences long at most, and ideally just a single sentence.
`;
        cohereChat(prompt, apiKey).then(response => {{ summaryContainer.innerHTML = response.text }} );
    }}
}}

function cohereSummaryCallback(selectedPoints) {{
    if (selectedPoints.length > 0) {{
        $(summaryContainer).animate({{width:'show'}}, {self.width});
    }} else {{
        $(summaryContainer).animate({{width:'hide'}}, {self.width});
    }}
    let selectedText;
    if (datamap.metaData) {{
        selectedText = selectedPoints.map(i => datamap.metaData.hover_text[i]);
    }} else {{
        selectedText = ["Meta data still loading ..."];
    }}
    generateSummary(selectedText);
}}

await datamap.addSelectionHandler(cohereSummaryCallback);
        """
        if self.other_triggers:
            for trigger in self.other_triggers:
                result += f"""await datamap.addSelectionHandler(cohereSummaryCallback, "{trigger}");\n"""
        return result

    @property
    def html(self):
        return ""

    @property
    def css(self):
        return f"""
#layout_container {{
    position: relative;
    display: flex;
    flex-direction: column;
    width: {self.width + 32}px;
}}
#summary-container {{
    display: none;
    width: {self.width - 24}px;
    height: fit-content;
    font-size: 16px;
    font-weight: 400;
    margin: 0px 16px 8px 16px;
    z-index: 10;
}}
#api-key-container {{
    align-self: end;
    width: fit-content;
    margin: 8px 16px 8px 16px;
    z-index: 10;
}}
"""


class TagSelection(SelectionHandlerBase):
    """
    A selection handler that allows users to create and save tags for selected items.
    The handler provides a container for displaying existing tags, a button to create a new tag,
    and a button to save the tags to a JSON file.

    The handler also provides a visual indicator for selected items that have been tagged, and
    allows users to add selected items to existing tags.

    Parameters
    ----------
    tag_colors : list, optional
        A list of colors to use for the tags. Default is a set of default colors extending the tab10 palette.

    location : str, optional
        The location of the tag container on the page. Default is "top-right".
        Should be one of "top-left", "top-right", "bottom-left", or "bottom-right".

    max_height : str, optional
        The maximum height of the tag container as a CSS descriptor string. Default is "95%".
    """

    def __init__(
        self,
        tag_colors=None,
        location="top-right",
        order=50,
        width=308,
        max_height="80vh",
        other_triggers=None,
        **kwargs,
    ):
        super().__init__(location=location, order=order, **kwargs)
        if tag_colors is None:
            self.tag_colors = _DEFAULT_TAG_COLORS
        else:
            self.tag_colors = tag_colors
        self.width = width
        self.max_height = max_height
        self.other_triggers = other_triggers

    @property
    def javascript(self):
        result = f"""
    const tagColors = [
    {",".join(['"'+x+'"' for x in self.tag_colors])}
    ];

    const tags = new Map();
    const tagStackContainer = document.getElementsByClassName("stack {self.location}")[0];
    const tagContainer = document.createElement("div");
    tagContainer.id = "tag-container";
    tagContainer.className = "container-box more-opaque stack-box";
    tagContainer.dataset.order = "{self.order}";
    const newTagSpan = document.createElement("span");
    const tagButton = document.createElement("button");
    tagButton.id = "new-tag-button";
    tagButton.className = "button tag-button";
    tagButton.textContent = "Create New Tag";
    tagButton.disabled = true;
    const tagInput = document.createElement("input");
    tagInput.id = "tag-input";
    tagInput.type = "text";
    tagInput.placeholder = "Enter tag name";
    tagInput.addEventListener("keypress", (event) => {{
        if (event.key === "Enter") {{
            createNewTag(datamap.getSelectedIndices());
        }}
    }});
    tagInput.disabled = true;
    newTagSpan.appendChild(tagButton);
    newTagSpan.appendChild(tagInput);
    tagContainer.appendChild(newTagSpan);
    const tagDisplay = document.createElement("div");
    tagDisplay.id = "tag-display";
    const tagList = document.createElement("ul");
    tagList.id = "tag-list";
    tagDisplay.appendChild(tagList);
    tagContainer.appendChild(tagDisplay);
    const saveTagsButton = document.createElement("button");
    saveTagsButton.id = "save-tags";
    saveTagsButton.className = "button tag-button enabled";
    saveTagsButton.textContent = "Save tags";
    tagContainer.appendChild(saveTagsButton);
    tagStackContainer.appendChild(tagContainer);
    const selectedTags = new Set();
    saveTagsButton.onclick = saveTags;
    let numTags = 0;
    
    function mapToObject(map) {{
        const obj = {{}};
        map.forEach((value, key) => {{
            obj[key] = Array.from(value);
        }});
        return obj;
    }}

    function saveTags() {{
        const tagsObject = mapToObject(tags);
        const jsonString = JSON.stringify(tagsObject, null, 2);
        const blob = new Blob([jsonString], {{ type: 'application/json' }});
        const url = URL.createObjectURL(blob);

        const a = document.createElement('a');
        a.href = url;
        a.download = 'tags.json';  // Specify the filename
        document.body.appendChild(a);
        a.click();
        URL.revokeObjectURL(url);
        document.body.removeChild(a);
    }}

    function toggleTagSelection(tagName) {{
        if (selectedTags.has(tagName)) {{
            selectedTags.delete(tagName);
        }} else {{
            selectedTags.add(tagName);
        }}
        if (selectedTags.size > 0) {{
            tagList.childNodes.forEach(tag => {{
                const tagName = tag.id.split("-")[1];
                if (selectedTags.has(tagName)) {{
                    tag.style.opacity = 1;
                }} else {{
                    tag.style.opacity = 0.25;
                }}
            }});
        }} else {{
            tagList.childNodes.forEach(tag => {{
                tag.style.opacity = 1;
            }});
        }}
        const selectedIndices = [];
        selectedTags.forEach(tag => {{
            tags.get(tag).forEach(index => {{
                selectedIndices.push(index);
            }});
        }});
        datamap.addSelection(selectedIndices, "tag-selection");
    }}

    function addSelectionToTag(tagName, selectedPoints) {{
        tags.set(tagName, tags.get(tagName).union(new Set(selectedPoints)));
        const addToTagButton = document.getElementById(`add-to-${{tagName}}`);
        addToTagButton.classList.remove("enabled");
        addToTagButton.style.display = "none";
        addToTagButton.disable = true;
    }}
    
    function createNewTag(selectedPoints) {{
        const tagName = tagInput.value;
        if (tags.has(tagName)) {{
            alert("Tag already exists! Try adding to the existing tag instead.");
        }} else if (tagName === "") {{
            alert("Tag name cannot be empty!");
        }} else {{
            addTag(tagName);
            tags.set(tagName, new Set(selectedPoints));
            tagInput.value = "";
        }}
    }}

    function addTag(tagName) {{
        const tagItem = document.createElement('li');
        tagItem.id = `tag-${{tagName}}`;
        tagItem.innerHTML = `
<div class="row">
  <div class="tag-info">
    <div 
        id="tag-selector-${{tagName}}" 
        class="box" 
        style="background-color: ${{tagColors[numTags]}};" 
    ></div>
    ${{tagName}}
  </div>
  <button id="add-to-${{tagName}}" class="button tag-button add-to-tag-button" style="display: none;">Add to tag</button>
</div>`;
        numTags += 1;
        tagList.appendChild(tagItem);
        document.getElementById(`tag-selector-${{tagName}}`).addEventListener("click", () => toggleTagSelection(tagName));
    }}

    function taggerCallback(selectedPoints) {{
        if (selectedPoints.length !== 0) {{
            tagButton.classList.add("enabled");
            tagButton.onclick = () => createNewTag(selectedPoints);
            tagButton.disabled = false;
            tagInput.disabled = false;
            tags.forEach((points, tagName, map) => {{
                    const addToTagButton = document.getElementById(`add-to-${{tagName}}`);
                    addToTagButton.onclick = () => addSelectionToTag(tagName, selectedPoints);
                    addToTagButton.classList.add("enabled");
                    addToTagButton.style.display = "block";
                    addToTagButton.disable = false;
            }});
        }} else {{
            tagButton.classList.remove("enabled");
            tagButton.disabled = true;
            tagInput.disabled = true;
            tags.forEach((points, tagName, map) => {{
                    const addToTagButton = document.getElementById(`add-to-${{tagName}}`);
                    addToTagButton.classList.remove("enabled");
                    addToTagButton.style.display = "none";
                    addToTagButton.disable = true;
            }});  
        }}
    }}

    await datamap.addSelectionHandler(taggerCallback);
        """
        if self.other_triggers:
            for trigger in self.other_triggers:
                result += f"""await datamap.addSelectionHandler(taggerCallback, "{trigger}");\n"""
        return result

    @property
    def html(self):
        return ""

    @property
    def css(self):
        return f"""
#tag-container {{
    position: relative;
    width: {self.width}px;
    height: fit-content;
    z-index: 10;
}}
#tag-display {{
    overflow-y: auto;
    margin: 8px;
    max-height: {self.max_height};
}}
.tag-button {{
    border: none;
    padding: 4px 8px;
    text-align: center; 
    display: inline-block;
    margin: 4px 2px;
    cursor: pointer;
    border-radius: 8px;
}}
.tag-button:enabled {{
    background-color: #3ba5e7;
    color: white;
}}
.tag-button:disabled {{
    background-color: #cccccc;
    color: #666666;
}}
#save-tags {{
  float: right;
}}
#tag-list {{
    list-style-type: none;
    width: 75%;
}}
.row {{
    display : flex;
    align-items : center;
    width: 100%;
    justify-content: space-between;
}}
.box {{
    height:10px;
    width:10px;
    border-radius:2px;
    margin-right:5px;
    padding:0px 0 1px 0;
    text-align:center;
    color: white;
    font-size: 14px;
}}
.tag-info {{
  display: flex;
  align-items: center;
}}
.add-to-tag-button {{
  float: right;
  font-size: 8px;
  padding: 2px 4px;
  margin: 0px 16px;
}}
    """


class DataTable(SelectionHandlerBase):
    """A selection handler that displays selected items in a sortable, filterable table with
    pagination and download capabilities. This handler displays all available metadata columns
    in a tabular format, allowing users to sort by any column, paginate through results, and
    export the data to CSV or JSON formats.

    The table is fully responsive and will adapt to the available space, with horizontal
    scrolling for wide tables. The "bottom-drawer" location is particularly well-suited for
    tables as it provides maximum width for viewing many columns.

    Parameters
    ----------
    columns : list of str or None, optional
        The list of metadata columns to display. If None, all available columns will be shown.
        Default is None.

    max_rows_per_page : int, optional
        The maximum number of rows to display per page. Default is 50.

    location : str, optional
        The location of the table container on the page. Default is "right-drawer".
        Should be one of "top-left", "top-right", "bottom-left", "bottom-right",
        "left-drawer", "right-drawer", or "bottom-drawer". Note: "bottom-drawer" is
        recommended for tables with many columns as it provides the most horizontal space.

    order : int, optional
        The stacking order within the location. Default is 20.

    show_index : bool, optional
        Whether to show the point index column. Default is True.

    sortable : bool, optional
        Whether columns should be sortable. Default is True.

    download_formats : list of str, optional
        The export formats to offer. Can include "csv" and/or "json". Default is ["csv", "json"].

    width : int, optional
        The width of the table container in pixels. Default is 700.

    **kwargs
        Additional keyword arguments to pass to the SelectionHandlerBase constructor.
    """

    @cfg.complete(unconfigurable={"self", "width", "max_rows_per_page"})
    def __init__(
        self,
        columns=None,
        max_rows_per_page=50,
        location="right-drawer",
        order=20,
        show_index=True,
        sortable=True,
        download_formats=None,
        width=700,
        cdn_url="unpkg.com",
        other_triggers=None,
        **kwargs,
    ):
        super().__init__(
            location=location,
            order=order,
            dependencies=[
                f"https://{cdn_url}/jquery@3.7.1/dist/jquery.min.js",
                # DataTables JS loaded dynamically after jQuery - see javascript property
                "https://cdn.datatables.net/1.13.8/css/jquery.dataTables.min.css",
            ],
            **kwargs,
        )
        self.datatables_js_url = (
            "https://cdn.datatables.net/1.13.8/js/jquery.dataTables.min.js"
        )
        self.columns = columns
        self.max_rows_per_page = max_rows_per_page
        self.show_index = show_index
        self.sortable = sortable
        self.download_formats = download_formats or ["csv", "json"]
        self.width = width
        self.other_triggers = other_triggers

    @property
    def javascript(self):
        columns_js = "null" if self.columns is None else str(self.columns)
        result = f"""
// DataTable selection handler using DataTables library
// Helper to find stack container or drawer
function findStackContainer(location) {{
    let stack = document.getElementsByClassName("stack " + location)[0];
    if (!stack && location.includes("drawer")) {{
        const drawerDirection = location.replace("-drawer", "");
        const drawer = document.querySelector(".drawer-container.drawer-" + drawerDirection);
        if (drawer) {{
            stack = drawer;
        }}
    }}
    return stack;
}}

const dataTableStackContainer = findStackContainer("{self.location}");
const dataTableContainer = document.createElement("div");
dataTableContainer.id = "data-table-container";
dataTableContainer.className = "container-box more-opaque stack-box";
dataTableContainer.dataset.order = "{self.order}";

// Download buttons
const tableControls = document.createElement("div");
tableControls.className = "table-controls";
"""
        if "csv" in self.download_formats:
            result += """
const csvButton = document.createElement("button");
csvButton.className = "table-button";
csvButton.textContent = "Download CSV";
csvButton.onclick = () => downloadTableData('csv');
tableControls.appendChild(csvButton);
"""
        if "json" in self.download_formats:
            result += """
const jsonButton = document.createElement("button");
jsonButton.className = "table-button";
jsonButton.textContent = "Download JSON";
jsonButton.onclick = () => downloadTableData('json');
tableControls.appendChild(jsonButton);
"""
        result += f"""

dataTableContainer.appendChild(tableControls);

// Table wrapper
const tableWrapper = document.createElement("div");
tableWrapper.className = "table-wrapper";
const table = document.createElement("table");
table.id = "selection-table";
table.className = "display compact stripe";
tableWrapper.appendChild(table);
dataTableContainer.appendChild(tableWrapper);

dataTableStackContainer.appendChild(dataTableContainer);

// Table state
let dataTable = null;
let tableColumns = {columns_js};

// Helper: Convert array of objects to CSV
function arrayToCSV(data, columns) {{
    if (data.length === 0) return '';
    
    const headers = columns.join(',');
    const rows = data.map(row => 
        columns.map(col => {{
            const value = row[col];
            if (value === null || value === undefined) return '';
            const stringValue = String(value);
            if (stringValue.includes(',') || stringValue.includes('"') || stringValue.includes('\\n')) {{
                return '"' + stringValue.replace(/"/g, '""') + '"';
            }}
            return stringValue;
        }}).join(',')
    );
    return headers + '\\n' + rows.join('\\n');
}}

// Download table data
function downloadTableData(format) {{
    if (!dataTable) {{
        alert('No data to download');
        return;
    }}
    
    const data = dataTable.rows().data().toArray();
    if (data.length === 0) {{
        alert('No data to download');
        return;
    }}
    
    let content, mimeType, filename;
    
    if (format === 'csv') {{
        content = arrayToCSV(data, tableColumns);
        mimeType = 'text/csv';
        filename = 'selection_data.csv';
    }} else if (format === 'json') {{
        content = JSON.stringify(data, null, 2);
        mimeType = 'application/json';
        filename = 'selection_data.json';
    }}
    
    const blob = new Blob([content], {{ type: mimeType }});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    URL.revokeObjectURL(url);
    document.body.removeChild(a);
}}

// DataTable callback
async function dataTableCallback(selectedPoints) {{
    if (!datamap.metaData) {{
        return;
    }}
    
    // Wait for jQuery to be loaded
    if (typeof jQuery === 'undefined' || typeof $ === 'undefined') {{
        console.log('Waiting for jQuery to load...');
        await new Promise(resolve => {{
            const checkJQuery = setInterval(() => {{
                if (typeof jQuery !== 'undefined' && typeof $ !== 'undefined') {{
                    clearInterval(checkJQuery);
                    resolve();
                }}
            }}, 100);
        }});
    }}
    
    // Dynamically load DataTables library after jQuery is ready
    if (typeof $.fn.DataTable === 'undefined') {{
        console.log('Loading DataTables library...');
        await new Promise((resolve, reject) => {{
            const script = document.createElement('script');
            script.src = '{self.datatables_js_url}';
            script.onload = () => {{
                console.log('DataTables loaded successfully');
                resolve();
            }};
            script.onerror = () => {{
                console.error('Failed to load DataTables');
                reject(new Error('Failed to load DataTables'));
            }};
            document.head.appendChild(script);
        }});
    }}
    
    // Destroy existing DataTable if it exists
    if (dataTable) {{
        dataTable.destroy();
        $('#selection-table').empty();
    }}
    
    if (selectedPoints.length === 0) {{
        return;
    }}
    
    // Determine columns if not specified
    if (tableColumns === null) {{
        tableColumns = Object.keys(datamap.metaData);
        if ({str(self.show_index).lower()}) {{
            tableColumns.unshift('index');
        }}
    }} else if ({str(self.show_index).lower()} && !tableColumns.includes('index')) {{
        tableColumns = ['index', ...tableColumns];
    }}
    
    // Build table data
    const tableData = selectedPoints.map(index => {{
        const row = {{}};
        if ({str(self.show_index).lower()}) {{
            row['index'] = index;
        }}
        tableColumns.forEach(col => {{
            if (col !== 'index' && datamap.metaData[col]) {{
                row[col] = datamap.metaData[col][index];
            }}
        }});
        return row;
    }});
    
    // Calculate responsive scroll height based on location
    let scrollHeight = '60vh';
    if ("{self.location}".includes("bottom")) {{
        // For bottom drawer (350px), account for controls, padding, and pagination
        // Drawer height 350px - padding 32px - controls ~40px - pagination ~50px = ~228px
        scrollHeight = '200px';
    }} else if ("{self.location}".includes("drawer")) {{
        scrollHeight = '50vh';
    }}
    
    // Initialize DataTables
    dataTable = $('#selection-table').DataTable({{
        data: tableData,
        columns: tableColumns.map(col => ({{ data: col, title: col }})),
        pageLength: {self.max_rows_per_page},
        lengthMenu: [[10, 25, 50, 100, -1], [10, 25, 50, 100, \"All\"]],
        ordering: {str(self.sortable).lower()},
        searching: true,
        info: true,
        autoWidth: false,
        scrollX: true,
        scrollY: scrollHeight,
        scrollCollapse: true,
        responsive: true,
        columnDefs: [
            {{
                targets: '_all',
                render: function(data, type, row) {{
                    if (type === 'display' && data && String(data).length > 100) {{
                        return '<span title=\"' + data + '\">' + String(data).substring(0, 97) + '...</span>';
                    }}
                    return data;
                }}
            }}
        ]
    }});
    
    // Open drawer if in drawer location
    if ("{self.location}".includes("drawer") && window.drawerManager) {{
        const drawerDirection = "{self.location}".replace("-drawer", "");
        window.drawerManager.openDrawer(drawerDirection);
    }}
}}

await datamap.addSelectionHandler(dataTableCallback);
"""
        if self.other_triggers:
            for trigger in self.other_triggers:
                result += f"""await datamap.addSelectionHandler(dataTableCallback, "{trigger}");\n"""
        return result

    @property
    def css(self):
        return f"""
#data-table-container {{
    width: 100%;
    max-width: 100%;
    padding: 12px;
    box-sizing: border-box;
    overflow: hidden;
}}

.table-controls {{
    display: flex;
    gap: 8px;
    margin-bottom: 12px;
    flex-wrap: wrap;
}}

.table-button {{
    padding: 4px 12px;
    background-color: #4CAF50;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
}}

.table-button:hover {{
    background-color: #45a049;
}}

.table-wrapper {{
    width: 100%;
    overflow-x: auto;
}}

/* DataTables overrides for better integration */
#selection-table {{
    font-size: 12px;
    width: 100% !important;
}}

.dataTables_wrapper {{
    width: 100%;
    overflow-x: auto;
}}

.dataTables_wrapper .dataTables_length,
.dataTables_wrapper .dataTables_filter,
.dataTables_wrapper .dataTables_info,
.dataTables_wrapper .dataTables_paginate {{
    font-size: 12px;
    margin-top: 8px;
}}

/* Responsive adjustments for different drawer locations */
.drawer-bottom #data-table-container {{
    max-height: 300px;
    height: auto;
}}

.drawer-right #data-table-container,
.drawer-left #data-table-container {{
    min-width: 400px;
}}

/* Stack containers */
.stack #data-table-container {{
    min-width: 350px;
    max-width: min(800px, 95vw);
}}
"""

    @property
    def html(self):
        return ""


class ExportSelection(SelectionHandlerBase):
    """A selection handler that provides simple export functionality for selected data.
    Allows exporting selected point indices, hover text, or full metadata in various formats
    including JSON, CSV, and TSV.

    Parameters
    ----------
    export_format : str, optional
        The default export format. One of "json", "csv", or "tsv". Default is "json".

    include_metadata : bool, optional
        Whether to include all metadata columns in the export. If False, only exports
        indices and hover_text (if available). Default is True.

    include_indices : bool, optional
        Whether to include the point indices in the export. Default is True.

    filename_prefix : str, optional
        The prefix to use for downloaded filenames. Default is "selection".

    location : str, optional
        The location of the export button on the page. Default is "top-right".
        Should be one of "top-left", "top-right", "bottom-left", or "bottom-right".

    order : int, optional
        The stacking order within the location. Default is 10.

    show_format_selector : bool, optional
        Whether to show a dropdown to select export format. If False, uses export_format.
        Default is True.

    **kwargs
        Additional keyword arguments to pass to the SelectionHandlerBase constructor.
    """

    @cfg.complete(unconfigurable={"self"})
    def __init__(
        self,
        export_format="json",
        include_metadata=True,
        include_indices=True,
        filename_prefix="selection",
        location="top-right",
        order=10,
        show_format_selector=True,
        other_triggers=None,
        **kwargs,
    ):
        super().__init__(
            location=location,
            order=order,
            **kwargs,
        )
        self.export_format = export_format
        self.include_metadata = include_metadata
        self.include_indices = include_indices
        self.filename_prefix = filename_prefix
        self.show_format_selector = show_format_selector
        self.other_triggers = other_triggers

    @property
    def javascript(self):
        result = f"""
// ExportSelection handler
// Helper to find stack container or drawer
function findStackContainer(location) {{
    let stack = document.getElementsByClassName("stack " + location)[0];
    if (!stack && location.includes("drawer")) {{
        const drawerDirection = location.replace("-drawer", "");
        const drawer = document.querySelector(".drawer-container.drawer-" + drawerDirection);
        if (drawer) {{
            stack = drawer;
        }}
    }}
    return stack;
}}

const exportStackContainer = findStackContainer("{self.location}");
const exportContainer = document.createElement("div");
exportContainer.id = "export-container";
exportContainer.className = "container-box more-opaque stack-box";
exportContainer.dataset.order = "{self.order}";

const exportTitle = document.createElement("div");
exportTitle.className = "export-title";
exportTitle.textContent = "Export Selection";
exportContainer.appendChild(exportTitle);

const exportControls = document.createElement("div");
exportControls.className = "export-controls";
"""
        if self.show_format_selector:
            result += """
const formatSelect = document.createElement("select");
formatSelect.id = "export-format";
formatSelect.className = "export-select";
formatSelect.innerHTML = `
    <option value="json">JSON</option>
    <option value="csv">CSV</option>
    <option value="tsv">TSV</option>
`;
"""
            result += f"""formatSelect.value = "{self.export_format}";\nexportControls.appendChild(formatSelect);\n"""

        result += """
const exportButton = document.createElement("button");
exportButton.id = "export-button";
exportButton.className = "export-button";
exportButton.textContent = "Export";
exportButton.disabled = true;
exportControls.appendChild(exportButton);

exportContainer.appendChild(exportControls);

const exportInfo = document.createElement("div");
exportInfo.id = "export-info";
exportInfo.className = "export-info";
exportInfo.textContent = "No selection";
exportContainer.appendChild(exportInfo);

exportStackContainer.appendChild(exportContainer);

let currentSelection = [];

// Helper: Convert to CSV/TSV
function arrayToDelimitedText(data, delimiter) {
    if (data.length === 0) return '';
    
    const keys = Object.keys(data[0]);
    const header = keys.join(delimiter);
    const rows = data.map(row => 
        keys.map(key => {
            const value = row[key];
            if (value === null || value === undefined) return '';
            const stringValue = String(value);
            // For CSV/TSV, escape if contains delimiter, quote, or newline
            if (stringValue.includes(delimiter) || stringValue.includes('"') || stringValue.includes('\\n')) {
                return '"' + stringValue.replace(/"/g, '""') + '"';
            }
            return stringValue;
        }).join(delimiter)
    );
    return header + '\\n' + rows.join('\\n');
}

// Export function
function exportSelectionData() {
    if (currentSelection.length === 0) {
        alert('No data to export');
        return;
    }
    
    if (!datamap.metaData) {
        alert('Metadata not loaded yet');
        return;
    }
    
"""
        format_expr = (
            "formatSelect.value"
            if self.show_format_selector
            else f'"{self.export_format}"'
        )
        result += f"""    const format = {format_expr};
    
    // Build export data
    const exportData = currentSelection.map(index => {{
        const row = {{}};
        """

        if self.include_indices:
            result += """
        row['index'] = index;
        """

        if self.include_metadata:
            result += """
        // Include all metadata columns
        Object.keys(datamap.metaData).forEach(col => {
            row[col] = datamap.metaData[col][index];
        });
        """
        else:
            result += """
        // Only include hover_text if available
        if (datamap.metaData.hover_text) {
            row['hover_text'] = datamap.metaData.hover_text[index];
        }
        """

        result += f"""
        return row;
    }});
    
    let content, mimeType, extension;
    
    if (format === 'json') {{
        content = JSON.stringify(exportData, null, 2);
        mimeType = 'application/json';
        extension = 'json';
    }} else if (format === 'csv') {{
        content = arrayToDelimitedText(exportData, ',');
        mimeType = 'text/csv';
        extension = 'csv';
    }} else if (format === 'tsv') {{
        content = arrayToDelimitedText(exportData, '\\t');
        mimeType = 'text/tab-separated-values';
        extension = 'tsv';
    }}
    
    const blob = new Blob([content], {{ type: mimeType }});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = '{self.filename_prefix}_' + currentSelection.length + '_items.' + extension;
    document.body.appendChild(a);
    a.click();
    URL.revokeObjectURL(url);
    document.body.removeChild(a);
}}

exportButton.onclick = exportSelectionData;

// Export callback
function exportCallback(selectedPoints) {{
    currentSelection = selectedPoints;
    
    if (selectedPoints.length === 0) {{
        exportButton.disabled = true;
        exportInfo.textContent = 'No selection';
    }} else {{
        exportButton.disabled = false;
        exportInfo.textContent = `${{selectedPoints.length}} points selected`;
    }}
}}

await datamap.addSelectionHandler(exportCallback);
"""
        if self.other_triggers:
            for trigger in self.other_triggers:
                result += f"""await datamap.addSelectionHandler(exportCallback, "{trigger}");\n"""
        return result

    @property
    def css(self):
        return """
#export-container {
    padding: 12px;
    width: fit-content;
    min-width: 200px;
}

.export-title {
    font-weight: bold;
    margin-bottom: 8px;
    font-size: 14px;
}

.export-controls {
    display: flex;
    gap: 8px;
    align-items: center;
    margin-bottom: 8px;
}

.export-select {
    padding: 4px 8px;
    border: 1px solid #ccc;
    border-radius: 4px;
    background-color: white;
    font-size: 12px;
}

.export-button {
    padding: 6px 16px;
    background-color: #4CAF50;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 12px;
    font-weight: bold;
}

.export-button:hover:not(:disabled) {
    background-color: #45a049;
}

.export-button:disabled {
    background-color: #cccccc;
    color: #666666;
    cursor: not-allowed;
}

.export-info {
    font-size: 11px;
    color: #666;
    font-style: italic;
}

/* Dark mode support */
.darkmode .export-select,
body.darkmode .export-select {
    background-color: #2d2d2d;
    color: #e0e0e0;
    border-color: #555;
}

.darkmode .export-info,
body.darkmode .export-info {
    color: #aaa;
}
"""

    @property
    def html(self):
        return ""


class Statistics(SelectionHandlerBase):
    """A selection handler that displays statistical summaries of the selected data compared
    to the overall dataset. Shows selection size, and if text data is available, provides
    text statistics such as average word count and unique words. Can also compute statistics
    for numeric columns if present in the metadata.

    Parameters
    ----------
    numeric_columns : list of str or None, optional
        List of numeric metadata columns to compute statistics for. If None, will attempt
        to auto-detect numeric columns. Default is None.

    categorical_columns : list of str or None, optional
        List of categorical metadata columns to show distribution for. If None, no categorical
        distributions are shown. Default is None.

    show_text_stats : bool, optional
        Whether to compute and show text statistics (word counts, unique words) from hover_text.
        Default is True.

    location : str, optional
        The location of the statistics container on the page. Default is "top-right".
        Should be one of "top-left", "top-right", "bottom-left", or "bottom-right".

    order : int, optional
        The stacking order within the location. Default is 50.

    width : int, optional
        The width of the statistics container in pixels. Default is 350.

    **kwargs
        Additional keyword arguments to pass to the SelectionHandlerBase constructor.
    """

    @cfg.complete(unconfigurable={"self", "width"})
    def __init__(
        self,
        numeric_columns=None,
        categorical_columns=None,
        show_text_stats=True,
        location="top-right",
        order=50,
        width=350,
        other_triggers=None,
        **kwargs,
    ):
        super().__init__(
            location=location,
            order=order,
            **kwargs,
        )
        self.numeric_columns = numeric_columns
        self.categorical_columns = categorical_columns
        self.show_text_stats = show_text_stats
        self.width = width
        self.other_triggers = other_triggers

    @property
    def javascript(self):
        numeric_cols_js = (
            "null" if self.numeric_columns is None else str(self.numeric_columns)
        )
        categorical_cols_js = (
            "null"
            if self.categorical_columns is None
            else str(self.categorical_columns)
        )

        result = f"""
// Statistics handler
// Helper to find stack container or drawer
function findStackContainer(location) {{
    let stack = document.getElementsByClassName("stack " + location)[0];
    if (!stack && location.includes("drawer")) {{
        const drawerDirection = location.replace("-drawer", "");
        const drawer = document.querySelector(".drawer-container.drawer-" + drawerDirection);
        if (drawer) {{
            stack = drawer;
        }}
    }}
    return stack;
}}

const statsStackContainer = findStackContainer("{self.location}");
const statsContainer = document.createElement("div");
statsContainer.id = "stats-container";
statsContainer.className = "container-box more-opaque stack-box";
statsContainer.dataset.order = "{self.order}";

const statsTitle = document.createElement("div");
statsTitle.className = "stats-title";
statsTitle.textContent = "Selection Statistics";
statsContainer.appendChild(statsTitle);

const statsContent = document.createElement("div");
statsContent.id = "stats-content";
statsContent.className = "stats-content";
statsContainer.appendChild(statsContent);

statsStackContainer.appendChild(statsContainer);

let globalStats = {{}};
let numericColumns = {numeric_cols_js};
let categoricalColumns = {categorical_cols_js};

// Helper: Compute basic statistics
function computeStats(values) {{
    if (values.length === 0) return null;
    
    const numericValues = values.map(Number).filter(v => !isNaN(v));
    if (numericValues.length === 0) return null;
    
    const sorted = numericValues.slice().sort((a, b) => a - b);
    const sum = sorted.reduce((a, b) => a + b, 0);
    const mean = sum / sorted.length;
    
    const variance = sorted.reduce((acc, val) => acc + Math.pow(val - mean, 2), 0) / sorted.length;
    const std = Math.sqrt(variance);
    
    const median = sorted.length % 2 === 0
        ? (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2
        : sorted[Math.floor(sorted.length / 2)];
    
    return {{
        count: sorted.length,
        mean: mean,
        std: std,
        min: sorted[0],
        max: sorted[sorted.length - 1],
        median: median
    }};
}}

// Helper: Compute text statistics
function computeTextStats(texts) {{
    const wordCounts = texts.map(text => text.split(/\\s+/).filter(w => w.length > 0).length);
    const totalWords = wordCounts.reduce((a, b) => a + b, 0);
    const avgWords = totalWords / texts.length;
    
    const allWords = new Set();
    texts.forEach(text => {{
        text.toLowerCase().split(/\\s+/).forEach(word => {{
            if (word.length > 0) allWords.add(word);
        }});
    }});
    
    return {{
        avgWords: avgWords,
        totalWords: totalWords,
        uniqueWords: allWords.size
    }};
}}

// Initialize global statistics
function initGlobalStats() {{
    if (!datamap.metaData) return;
    
    // Auto-detect numeric columns if not specified
    if (numericColumns === null) {{
        numericColumns = [];
        Object.keys(datamap.metaData).forEach(col => {{
            if (col === 'hover_text') return;
            const sample = datamap.metaData[col].slice(0, 100);
            const numericCount = sample.filter(v => !isNaN(Number(v))).length;
            if (numericCount / sample.length > 0.8) {{
                numericColumns.push(col);
            }}
        }});
    }}
    
    // Compute global stats for numeric columns
    if (numericColumns && numericColumns.length > 0) {{
        numericColumns.forEach(col => {{
            if (datamap.metaData[col]) {{
                globalStats[col] = computeStats(datamap.metaData[col]);
            }}
        }});
    }}
    
    // Compute global text stats
    if ({str(self.show_text_stats).lower()} && datamap.metaData.hover_text) {{
        globalStats['text'] = computeTextStats(datamap.metaData.hover_text);
    }}
}}

// Render statistics
function renderStats(selectedPoints) {{
    if (selectedPoints.length === 0) {{
        statsContent.innerHTML = '<div class="stats-item">No selection</div>';
        return;
    }}
    
    let html = '';
    
    // Basic counts
    const totalPoints = datamap.metaData.hover_text ? datamap.metaData.hover_text.length : 0;
    const percentage = totalPoints > 0 ? ((selectedPoints.length / totalPoints) * 100).toFixed(1) : 0;
    html += `
        <div class="stats-section">
            <div class="stats-section-title">Selection Size</div>
            <div class="stats-item"><strong>${{selectedPoints.length}}</strong> of ${{totalPoints}} points (${{percentage}}%)</div>
        </div>
    `;
    
    // Text statistics
    if ({str(self.show_text_stats).lower()} && datamap.metaData.hover_text) {{
        const selectedTexts = selectedPoints.map(i => datamap.metaData.hover_text[i]);
        const selectionTextStats = computeTextStats(selectedTexts);
        
        html += `
            <div class="stats-section">
                <div class="stats-section-title">Text Statistics</div>
                <div class="stats-item">Avg words per item: <strong>${{selectionTextStats.avgWords.toFixed(1)}}</strong>`;
        if (globalStats.text) {{
            html += ` (global: ${{globalStats.text.avgWords.toFixed(1)}})`;
        }}
        html += `</div>
                <div class="stats-item">Total words: <strong>${{selectionTextStats.totalWords}}</strong>`;
        if (globalStats.text) {{
            html += ` (global: ${{globalStats.text.totalWords}})`;
        }}
        html += `</div>
                <div class="stats-item">Unique words: <strong>${{selectionTextStats.uniqueWords}}</strong>`;
        if (globalStats.text) {{
            html += ` (global: ${{globalStats.text.uniqueWords}})`;
        }}
        html += `</div>
            </div>
        `;
    }}
    
    // Numeric column statistics
    if (numericColumns && numericColumns.length > 0) {{
        numericColumns.forEach(col => {{
            if (!datamap.metaData[col]) return;
            
            const selectedValues = selectedPoints.map(i => datamap.metaData[col][i]);
            const selectionStats = computeStats(selectedValues);
            
            if (selectionStats) {{
                html += `
                    <div class="stats-section">
                        <div class="stats-section-title">${{col}}</div>
                        <div class="stats-item">Mean: <strong>${{selectionStats.mean.toFixed(2)}}</strong>`;
                if (globalStats[col]) {{
                    html += ` (global: ${{globalStats[col].mean.toFixed(2)}})`;
                }}
                html += `</div>
                        <div class="stats-item">Median: <strong>${{selectionStats.median.toFixed(2)}}</strong>`;
                if (globalStats[col]) {{
                    html += ` (global: ${{globalStats[col].median.toFixed(2)}})`;
                }}
                html += `</div>
                        <div class="stats-item">Std: <strong>${{selectionStats.std.toFixed(2)}}</strong>`;
                if (globalStats[col]) {{
                    html += ` (global: ${{globalStats[col].std.toFixed(2)}})`;
                }}
                html += `</div>
                        <div class="stats-item">Range: <strong>${{selectionStats.min.toFixed(2)}}</strong> to <strong>${{selectionStats.max.toFixed(2)}}</strong></div>
                    </div>
                `;
            }}
        }});
    }}
    
    // Categorical distributions
    if (categoricalColumns && categoricalColumns.length > 0) {{
        categoricalColumns.forEach(col => {{
            if (!datamap.metaData[col]) return;
            
            const selectedValues = selectedPoints.map(i => datamap.metaData[col][i]);
            const counts = {{}};
            selectedValues.forEach(val => {{
                counts[val] = (counts[val] || 0) + 1;
            }});
            
            const sorted = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 5);
            
            html += `
                <div class="stats-section">
                    <div class="stats-section-title">${{col}} (top 5)</div>
            `;
            sorted.forEach(([val, count]) => {{
                const pct = ((count / selectedPoints.length) * 100).toFixed(1);
                html += `<div class="stats-item">${{val}}: <strong>${{count}}</strong> (${{pct}}%)</div>`;
            }});
            html += `</div>`;
        }});
    }}
    
    statsContent.innerHTML = html;
}}

// Statistics callback
function statsCallback(selectedPoints) {{
    if (!datamap.metaData) {{
        statsContent.innerHTML = '<div class="stats-item">Loading metadata...</div>';
        return;
    }}
    
    // Initialize global stats on first call
    if (Object.keys(globalStats).length === 0) {{
        initGlobalStats();
    }}
    
    renderStats(selectedPoints);
}}

await datamap.addSelectionHandler(statsCallback);
"""
        if self.other_triggers:
            for trigger in self.other_triggers:
                result += f"""await datamap.addSelectionHandler(statsCallback, "{trigger}");\n"""
        return result

    @property
    def css(self):
        return f"""
#stats-container {{
    width: {self.width}px;
    padding: 12px;
}}

.stats-title {{
    font-weight: bold;
    font-size: 14px;
    margin-bottom: 12px;
    border-bottom: 2px solid #4CAF50;
    padding-bottom: 4px;
}}

.stats-content {{
    max-height: 50vh;
    overflow-y: auto;
}}

.stats-section {{
    margin-bottom: 16px;
}}

.stats-section-title {{
    font-weight: bold;
    font-size: 12px;
    color: #4CAF50;
    margin-bottom: 6px;
}}

.stats-item {{
    font-size: 11px;
    padding: 3px 0;
    color: #444;
}}

.stats-item strong {{
    color: #000;
}}

/* Dark mode support */
.darkmode .stats-title,
body.darkmode .stats-title {{
    border-bottom-color: #45a049;
}}

.darkmode .stats-section-title,
body.darkmode .stats-section-title {{
    color: #5FD068;
}}

.darkmode .stats-item,
body.darkmode .stats-item {{
    color: #ccc;
}}

.darkmode .stats-item strong,
body.darkmode .stats-item strong {{
    color: #fff;
}}
"""

    @property
    def html(self):
        return ""


class Histogram(SelectionHandlerBase):
    """A selection handler that displays histograms or bar charts showing the distribution
    of selected data across one or more fields. Supports multiple visualization modes for
    comparing distributions across fields.

    For categorical fields, displays bar charts of category frequencies. For numeric fields,
    displays histograms with configurable bins. Supports up to 5 fields simultaneously with
    various display modes:

    - **Small Multiples**: Separate stacked subplots for each field
    - **Overlaid**: Semi-transparent overlapping histograms on shared axes
    - **Normalized**: All histograms scaled to 0-1 range for comparison
    - **Grouped Bars**: Side-by-side bars (for categorical data)
    - **Separate Charts**: Individual bar charts stacked vertically (categorical)
    - **Faceted**: Side-by-side small bar charts (categorical)

    Parameters
    ----------
    field : str, list of str, or None, optional
        The metadata field(s) to create histograms for. Can be a single field name,
        a list of field names, or None. If None, starts with first available non-hover_text
        field. Default is None.

    bins : int, optional
        Number of bins for numeric field histograms. Default is 20.

    max_fields : int, optional
        Maximum number of fields that can be displayed simultaneously. Default is 5.

    default_mode : str, optional
        Default visualization mode. Options: "overlaid", "small-multiples", "normalized",
        "grouped", "separate", "faceted". Default is "overlaid".

    show_comparison : bool, optional
        Whether to show the overall dataset distribution for comparison (deprecated in
        multi-field mode). Default is False.

    max_categories : int, optional
        Maximum number of categories to show in categorical bar charts. Default is 10.

    location : str, optional
        The location of the histogram container on the page. Default is "bottom-right".
        Should be one of "top-left", "top-right", "bottom-left", or "bottom-right".

    order : int, optional
        The stacking order within the location. Default is 40.

    width : int, optional
        The width of the histogram container in pixels. Default is 500.

    height : int, optional
        The height of the histogram chart in pixels. Default is 400.

    **kwargs
        Additional keyword arguments to pass to the SelectionHandlerBase constructor.
    """

    @cfg.complete(unconfigurable={"self", "width", "height", "bins"})
    def __init__(
        self,
        field=None,
        bins=20,
        max_fields=5,
        default_mode="overlaid",
        show_comparison=False,
        max_categories=10,
        location="bottom-right",
        order=40,
        width=500,
        height=400,
        cdn_url="unpkg.com",
        other_triggers=None,
        **kwargs,
    ):
        super().__init__(
            location=location,
            order=order,
            dependencies=[
                f"https://{cdn_url}/d3@latest/dist/d3.min.js",
            ],
            **kwargs,
        )
        # Support both single field and list of fields
        if isinstance(field, list):
            self.initial_fields = field
        elif field is not None:
            self.initial_fields = [field]
        else:
            self.initial_fields = []

        self.bins = bins
        self.max_fields = max_fields
        self.default_mode = default_mode
        self.show_comparison = show_comparison
        self.max_categories = max_categories
        self.width = width
        self.height = height
        self.other_triggers = other_triggers

    @property
    def javascript(self):
        initial_fields_js = str(self.initial_fields)  # Python list becomes JS array

        result = f"""
// Histogram handler - Multi-field visualization
// Tableau 10 color palette
const TABLEAU_COLORS = [
    '#4e79a7', '#f28e2c', '#e15759', '#76b7b2', '#59a14f',
    '#edc949', '#af7aa1', '#ff9da7', '#9c755f', '#bab0ab'
];

// Helper to find stack container or drawer
function findStackContainer(location) {{
    let stack = document.getElementsByClassName("stack " + location)[0];
    if (!stack && location.includes("drawer")) {{
        const drawerDirection = location.replace("-drawer", "");
        const drawer = document.querySelector(".drawer-container.drawer-" + drawerDirection);
        if (drawer) {{
            stack = drawer;
        }}
    }}
    return stack;
}}

const histogramStackContainer = findStackContainer("{self.location}");
const histogramContainer = document.createElement("div");
histogramContainer.id = "histogram-container";
histogramContainer.className = "container-box more-opaque stack-box";
histogramContainer.dataset.order = "{self.order}";

const histogramTitle = document.createElement("div");
histogramTitle.className = "histogram-title";
histogramTitle.textContent = "Distribution";
histogramContainer.appendChild(histogramTitle);

// Field selector controls wrapper
const controlsWrapper = document.createElement("div");
controlsWrapper.className = "histogram-controls";
histogramContainer.appendChild(controlsWrapper);

// Add field dropdown
const fieldSelector = document.createElement("select");
fieldSelector.id = "histogram-field-select";
fieldSelector.className = "histogram-select";
const defaultOption = document.createElement("option");
defaultOption.value = "";
defaultOption.textContent = "➕ Add field...";
fieldSelector.appendChild(defaultOption);
controlsWrapper.appendChild(fieldSelector);

// Mode selector dropdown
const modeSelector = document.createElement("select");
modeSelector.id = "histogram-mode-select";
modeSelector.className = "histogram-mode-select";
controlsWrapper.appendChild(modeSelector);

// Chip container
const chipContainer = document.createElement("div");
chipContainer.id = "histogram-chips";
chipContainer.className = "histogram-chips";
histogramContainer.appendChild(chipContainer);

// Warning message area
const warningContainer = document.createElement("div");
warningContainer.id = "histogram-warning";
warningContainer.className = "histogram-warning";
warningContainer.style.display = "none";
histogramContainer.appendChild(warningContainer);

// Append container to DOM BEFORE creating D3 SVG
histogramStackContainer.appendChild(histogramContainer);

const histogramSvg = d3.select("#histogram-container").append("svg")
    .attr("width", {self.width})
    .attr("height", {self.height})
    .attr("class", "histogram-svg");

// State variables
let selectedFields = {initial_fields_js};
let availableFields = [];
let fieldColors = {{}};
let currentMode = "{self.default_mode}";
let currentSelection = [];
const MAX_FIELDS = {self.max_fields};

const margin = {{top: 20, right: 20, bottom: 40, left: 50}};
const chartWidth = {self.width} - margin.left - margin.right;
const chartHeight = {self.height} - margin.top - margin.bottom;

// ============ Utility Functions ============

// Get consistent color for a field
function getFieldColor(field) {{
    if (!fieldColors[field]) {{
        const colorIndex = Object.keys(fieldColors).length % TABLEAU_COLORS.length;
        fieldColors[field] = TABLEAU_COLORS[colorIndex];
    }}
    return fieldColors[field];
}}

// Add a field to selection
function addField(field) {{
    if (!field || selectedFields.includes(field)) return;
    if (selectedFields.length >= MAX_FIELDS) {{
        warningContainer.textContent = `Maximum ${{MAX_FIELDS}} fields allowed`;
        warningContainer.style.display = "block";
        setTimeout(() => {{ warningContainer.style.display = "none"; }}, 3000);
        return;
    }}
    selectedFields.push(field);
    getFieldColor(field); // Assign color
    renderChips();
    updateFieldSelector();  // Update dropdown to exclude this field
    updateModeOptions();
    if (currentSelection.length > 0) {{
        renderHistogram(currentSelection);
    }}
    // Reset dropdown
    fieldSelector.value = "";
}}

// Remove a field from selection
function removeField(field) {{
    const index = selectedFields.indexOf(field);
    if (index > -1) {{
        selectedFields.splice(index, 1);
        renderChips();
        updateFieldSelector();  // Update dropdown to include this field again
        updateModeOptions();
        if (currentSelection.length > 0) {{
            renderHistogram(currentSelection);
        }} else {{
            histogramSvg.selectAll("*").remove();
        }}
    }}
}}

// Render chip/tag elements
function renderChips() {{
    chipContainer.innerHTML = "";
    if (selectedFields.length === 0) {{
        chipContainer.style.display = "none";
        return;
    }}
    chipContainer.style.display = "flex";
    
    selectedFields.forEach(field => {{
        const chip = document.createElement("div");
        chip.className = "histogram-chip";
        chip.style.backgroundColor = getFieldColor(field);
        chip.style.color = "#fff";
        
        const label = document.createElement("span");
        label.textContent = field;
        chip.appendChild(label);
        
        const removeBtn = document.createElement("button");
        removeBtn.className = "chip-remove";
        removeBtn.innerHTML = "×";
        removeBtn.onclick = (e) => {{
            e.stopPropagation();
            removeField(field);
        }};
        chip.appendChild(removeBtn);
        
        chipContainer.appendChild(chip);
    }});
}}

// Update available visualization modes based on selected field types
function updateModeOptions() {{
    if (selectedFields.length === 0) {{
        modeSelector.style.display = "none";
        return;
    }}
    modeSelector.style.display = "inline-block";
    
    // Detect field types
    let allNumeric = true;
    let allCategorical = true;
    
    selectedFields.forEach(field => {{
        if (!datamap.metaData || !datamap.metaData[field]) return;
        const values = datamap.metaData[field].slice(0, 100);
        const numericCount = values.filter(v => !isNaN(Number(v)) && v !== null && v !== '').length;
        const isNumeric = numericCount / values.length > 0.8;
        
        if (isNumeric) allCategorical = false;
        else allNumeric = false;
    }});
    
    // Build mode options
    modeSelector.innerHTML = "";
    
    if (allNumeric) {{
        addModeOption("overlaid", "Overlaid");
        addModeOption("small-multiples", "Small Multiples");
        addModeOption("normalized", "Normalized");
    }} else if (allCategorical) {{
        addModeOption("grouped", "Grouped Bars");
        addModeOption("separate", "Separate Charts");
        addModeOption("faceted", "Faceted");
    }} else {{
        // Mixed types - show generic options
        addModeOption("small-multiples", "Small Multiples");
        addModeOption("separate", "Separate");
    }}
    
    // Set current mode if valid, otherwise first option
    if (!Array.from(modeSelector.options).some(opt => opt.value === currentMode)) {{
        currentMode = modeSelector.options[0].value;
    }}
    modeSelector.value = currentMode;
}}

function addModeOption(value, label) {{
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    modeSelector.appendChild(option);
}}

// Detect field type
function isNumericField(values) {{
    const sample = values.slice(0, 100);
    const numericCount = sample.filter(v => !isNaN(Number(v)) && v !== null && v !== '').length;
    return numericCount / sample.length > 0.8;
}}

// Create histogram bins
function createHistogramBins(values, nBins) {{
    const numericValues = values.map(Number).filter(v => !isNaN(v));
    if (numericValues.length === 0) return [];
    
    const min = Math.min(...numericValues);
    const max = Math.max(...numericValues);
    const binWidth = (max - min) / nBins;
    
    const bins = Array.from({{ length: nBins }}, (_, i) => ({{
        x0: min + i * binWidth,
        x1: min + (i + 1) * binWidth,
        count: 0
    }}));
    
    numericValues.forEach(val => {{
        const binIndex = Math.min(Math.floor((val - min) / binWidth), nBins - 1);
        if (binIndex >= 0) bins[binIndex].count++;
    }});
    
    return bins;
}}

// Create categorical distribution
function createCategoricalDistribution(values, maxCategories) {{
    const counts = {{}};
    values.forEach(val => {{
        const key = val === null || val === undefined ? '(null)' : String(val);
        counts[key] = (counts[key] || 0) + 1;
    }});
    
    const sorted = Object.entries(counts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, maxCategories);
    
    return sorted.map(([category, count]) => ({{ category, count }}));
}}

// Initialize available fields
function initializeFields() {{
    if (!datamap.metaData) return;
    
    availableFields = Object.keys(datamap.metaData).filter(key => key !== 'hover_text');
    
    if (availableFields.length === 0) return;
    
    // Populate field selector dropdown (excluding already selected)
    updateFieldSelector();
    
    // Set up event handlers
    fieldSelector.onchange = (e) => {{
        if (e.target.value) {{
            addField(e.target.value);
        }}
    }};
    
    modeSelector.onchange = (e) => {{
        currentMode = e.target.value;
        if (currentSelection.length > 0) {{
            renderHistogram(currentSelection);
        }}
    }};
    
    // Initialize with specified fields or first available
    if (selectedFields.length === 0 && availableFields.length > 0) {{
        selectedFields = [availableFields[0]];
        getFieldColor(selectedFields[0]);
    }}
    
    renderChips();
    updateModeOptions();
}}

// Update field selector to exclude already selected fields
function updateFieldSelector() {{
    // Keep the default "Add field..." option
    const currentValue = fieldSelector.value;
    const defaultOption = fieldSelector.options[0];
    fieldSelector.innerHTML = "";
    fieldSelector.appendChild(defaultOption);
    
    // Add available fields that aren't already selected
    availableFields
        .filter(field => !selectedFields.includes(field))
        .forEach(field => {{
            const option = document.createElement("option");
            option.value = field;
            option.textContent = field;
            fieldSelector.appendChild(option);
        }});
    
    fieldSelector.value = "";  // Reset to default
}}

// ============ Main Rendering Functions ============

// Render histogram
function renderHistogram(selectedPoints) {{
    if (selectedFields.length === 0) {{
        histogramSvg.selectAll("*").remove();
        return;
    }}
    
    currentSelection = selectedPoints;
    
    // Clear previous render
    histogramSvg.selectAll("*").remove();
    
    // Check for range warnings (numeric fields only)
    checkRangeWarnings(selectedPoints);
    
    // Route to appropriate renderer based on mode
    switch(currentMode) {{
        case 'overlaid':
            renderOverlaid(selectedPoints);
            break;
        case 'small-multiples':
            renderSmallMultiples(selectedPoints);
            break;
        case 'normalized':
            renderNormalized(selectedPoints);
            break;
        case 'grouped':
            renderGroupedBars(selectedPoints);
            break;
        case 'separate':
            renderSeparate(selectedPoints);
            break;
        case 'faceted':
            renderFaceted(selectedPoints);
            break;
        default:
            renderOverlaid(selectedPoints);
    }}
}}

// Check if numeric ranges differ significantly
function checkRangeWarnings(selectedPoints) {{
    const numericFields = selectedFields.filter(field => {{
        if (!datamap.metaData || !datamap.metaData[field]) return false;
        const values = selectedPoints.map(i => datamap.metaData[field][i]).filter(v => v !== null);
        return isNumericField(values);
    }});
    
    if (numericFields.length < 2) {{
        warningContainer.style.display = "none";
        return;
    }}
    
    // Calculate range ratios
    const ranges = numericFields.map(field => {{
        const values = selectedPoints
            .map(i => datamap.metaData[field][i])
            .map(Number)
            .filter(v => !isNaN(v));
        const min = Math.min(...values);
        const max = Math.max(...values);
        return max - min;
    }});
    
    const maxRange = Math.max(...ranges);
    const minRange = Math.min(...ranges.filter(r => r > 0));
    
    if (maxRange / minRange > 100 && currentMode === 'overlaid') {{
        warningContainer.textContent = "⚠ Field ranges differ significantly. Consider 'Normalized' or 'Small Multiples' mode.";
        warningContainer.style.display = "block";
    }} else {{
        warningContainer.style.display = "none";
    }}
}}

// ============ Rendering Mode Implementations ============

// Overlaid mode: Semi-transparent overlapping histograms
function renderOverlaid(selectedPoints) {{
    const g = histogramSvg.append("g")
        .attr("transform", `translate(${{margin.left}},${{margin.top}})`);
    
    // Collect data for all fields
    const fieldsData = selectedFields.map(field => {{
        const values = selectedPoints.map(i => datamap.metaData[field][i]).filter(v => v !== null);
        const isNumeric = isNumericField(values);
        
        if (isNumeric) {{
            return {{
                field,
                type: 'numeric',
                values,
                bins: createHistogramBins(values, {self.bins}),
                color: getFieldColor(field)
            }};
        }} else {{
            return {{
                field,
                type: 'categorical',
                values,
                distribution: createCategoricalDistribution(values, {self.max_categories}),
                color: getFieldColor(field)
            }};
        }}
    }});
    
    // Check if all numeric or all categorical
    const allNumeric = fieldsData.every(d => d.type === 'numeric');
    const allCategorical = fieldsData.every(d => d.type === 'categorical');
    
    if (allNumeric) {{
        renderOverlaidNumeric(g, fieldsData);
    }} else if (allCategorical) {{
        renderOverlaidCategorical(g, fieldsData);
    }} else {{
        // Mixed types - fall back to separate
        renderSeparate(selectedPoints);
    }}
}}

// Overlaid numeric histograms
function renderOverlaidNumeric(g, fieldsData) {{
    // Find global min/max across all fields
    const allBins = fieldsData.flatMap(d => d.bins);
    const globalMin = Math.min(...allBins.map(b => b.x0));
    const globalMax = Math.max(...allBins.map(b => b.x1));
    
    const x = d3.scaleLinear()
        .domain([globalMin, globalMax])
        .range([0, chartWidth]);
    
    const maxCount = Math.max(...allBins.map(b => b.count));
    const y = d3.scaleLinear()
        .domain([0, maxCount])
        .range([chartHeight, 0]);
    
    // Draw each field's histogram
    fieldsData.forEach(fieldData => {{
        g.selectAll(`.bar-${{fieldData.field.replace(/[^a-zA-Z0-9]/g, '_')}}`)
            .data(fieldData.bins)
            .enter().append("rect")
            .attr("class", `bar-${{fieldData.field.replace(/[^a-zA-Z0-9]/g, '_')}}`)
            .attr("x", d => x(d.x0))
            .attr("width", d => Math.max(0, x(d.x1) - x(d.x0) - 1))
            .attr("y", d => y(d.count))
            .attr("height", d => chartHeight - y(d.count))
            .attr("fill", fieldData.color)
            .attr("opacity", 0.6);
    }});
    
    // Axes
    g.append("g")
        .attr("transform", `translate(0,${{chartHeight}})`)
        .call(d3.axisBottom(x).ticks(5))
        .selectAll("text")
        .style("font-size", "10px");
    
    g.append("g")
        .call(d3.axisLeft(y).ticks(5))
        .selectAll("text")
        .style("font-size", "10px");
    
    // Y-axis label
    g.append("text")
        .attr("transform", "rotate(-90)")
        .attr("x", -chartHeight / 2)
        .attr("y", -35)
        .attr("text-anchor", "middle")
        .style("font-size", "11px")
        .text("Count");
}}

// Overlaid categorical (grouped bars)
function renderOverlaidCategorical(g, fieldsData) {{
    // For categorical, overlaid mode shows grouped bars
    renderGroupedBarsInternal(g, fieldsData);
}}

// Separate mode: Individual charts stacked vertically
function renderSeparate(selectedPoints) {{
    const numFields = selectedFields.length;
    const chartHeightEach = (chartHeight - (numFields - 1) * 10) / numFields;  // 10px gap
    
    selectedFields.forEach((field, i) => {{
        const values = selectedPoints.map(idx => datamap.metaData[field][idx]).filter(v => v !== null);
        const isNumeric = isNumericField(values);
        
        const g = histogramSvg.append("g")
            .attr("transform", `translate(${{margin.left}},${{margin.top + i * (chartHeightEach + 10)}})`);
        
        if (isNumeric) {{
            renderSingleNumericHistogram(g, field, values, chartHeightEach);
        }} else {{
            renderSingleCategoricalChart(g, field, values, chartHeightEach);
        }}
    }});
}}

// Single numeric histogram for separate/small multiples mode
function renderSingleNumericHistogram(g, field, values, height) {{
    const bins = createHistogramBins(values, {self.bins});
    
    const x = d3.scaleLinear()
        .domain([bins[0].x0, bins[bins.length - 1].x1])
        .range([0, chartWidth]);
    
    const y = d3.scaleLinear()
        .domain([0, Math.max(...bins.map(b => b.count))])
        .range([height, 0]);
    
    // Bars
    g.selectAll(".bar")
        .data(bins)
        .enter().append("rect")
        .attr("class", "bar")
        .attr("x", d => x(d.x0))
        .attr("width", d => Math.max(0, x(d.x1) - x(d.x0) - 1))
        .attr("y", d => y(d.count))
        .attr("height", d => height - y(d.count))
        .attr("fill", getFieldColor(field));
    
    // Axes
    g.append("g")
        .attr("transform", `translate(0,${{height}})`)
        .call(d3.axisBottom(x).ticks(3))
        .selectAll("text")
        .style("font-size", "9px");
    
    g.append("g")
        .call(d3.axisLeft(y).ticks(3))
        .selectAll("text")
        .style("font-size", "9px");
    
    // Field label
    g.append("text")
        .attr("x", chartWidth / 2)
        .attr("y", -5)
        .attr("text-anchor", "middle")
        .style("font-size", "10px")
        .style("font-weight", "bold")
        .style("fill", getFieldColor(field))
        .text(field);
}}

// Single categorical chart for separate mode
function renderSingleCategoricalChart(g, field, values, height) {{
    const distribution = createCategoricalDistribution(values, {self.max_categories});
    
    const x = d3.scaleBand()
        .domain(distribution.map(d => d.category))
        .range([0, chartWidth])
        .padding(0.2);
    
    const y = d3.scaleLinear()
        .domain([0, Math.max(...distribution.map(d => d.count))])
        .range([height, 0]);
    
    // Bars
    g.selectAll(".bar")
        .data(distribution)
        .enter().append("rect")
        .attr("class", "bar")
        .attr("x", d => x(d.category))
        .attr("width", x.bandwidth())
        .attr("y", d => y(d.count))
        .attr("height", d => height - y(d.count))
        .attr("fill", getFieldColor(field));
    
    // Axes
    g.append("g")
        .attr("transform", `translate(0,${{height}})`)
        .call(d3.axisBottom(x))
        .selectAll("text")
        .attr("transform", "rotate(-45)")
        .style("text-anchor", "end")
        .style("font-size", "8px");
    
    g.append("g")
        .call(d3.axisLeft(y).ticks(3))
        .selectAll("text")
        .style("font-size", "9px");
    
    // Field label
    g.append("text")
        .attr("x", chartWidth / 2)
        .attr("y", -5)
        .attr("text-anchor", "middle")
        .style("font-size", "10px")
        .style("font-weight", "bold")
        .style("fill", getFieldColor(field))
        .text(field);
}}

// Small Multiples mode (alias for separate with better spacing)
function renderSmallMultiples(selectedPoints) {{
    renderSeparate(selectedPoints);
}}

// Normalized mode: Scale all to 0-1
function renderNormalized(selectedPoints) {{
    const g = histogramSvg.append("g")
        .attr("transform", `translate(${{margin.left}},${{margin.top}})`);
    
    // Collect and normalize data
    const fieldsData = selectedFields.map(field => {{
        const values = selectedPoints.map(i => datamap.metaData[field][i]).filter(v => v !== null);
        const bins = createHistogramBins(values, {self.bins});
        
        // Normalize to 0-1
        const maxCount = Math.max(...bins.map(b => b.count));
        const normalizedBins = bins.map(b => ({{
            ...b,
            normalizedCount: maxCount > 0 ? b.count / maxCount : 0
        }}));
        
        return {{
            field,
            bins: normalizedBins,
            color: getFieldColor(field)
        }};
    }});
    
    // Common scale (0-1 for normalized data)
    const y = d3.scaleLinear()
        .domain([0, 1])
        .range([chartHeight, 0]);
    
    // Each field gets its own x-scale based on its data range
    fieldsData.forEach(fieldData => {{
        const bins = fieldData.bins;
        const x = d3.scaleLinear()
            .domain([bins[0].x0, bins[bins.length - 1].x1])
            .range([0, chartWidth]);
        
        g.selectAll(`.bar-${{fieldData.field.replace(/[^a-zA-Z0-9]/g, '_')}}`)
            .data(bins)
            .enter().append("rect")
            .attr("x", d => x(d.x0))
            .attr("width", d => Math.max(0, x(d.x1) - x(d.x0) - 1))
            .attr("y", d => y(d.normalizedCount))
            .attr("height", d => chartHeight - y(d.normalizedCount))
            .attr("fill", fieldData.color)
            .attr("opacity", 0.6);
    }});
    
    // Axes
    g.append("g")
        .attr("transform", `translate(0,${{chartHeight}})`)
        .call(d3.axisBottom(d3.scaleLinear().domain([0, 1]).range([0, chartWidth])).ticks(5))
        .selectAll("text")
        .style("font-size", "10px");
    
    g.append("g")
        .call(d3.axisLeft(y).ticks(5).tickFormat(d => `${{(d * 100).toFixed(0)}}%`))
        .selectAll("text")
        .style("font-size", "10px");
    
    // Labels
    g.append("text")
        .attr("transform", "rotate(-90)")
        .attr("x", -chartHeight / 2)
        .attr("y", -35)
        .attr("text-anchor", "middle")
        .style("font-size", "11px")
        .text("Normalized (%)");
}}

// Grouped Bars mode (for categorical)
function renderGroupedBars(selectedPoints) {{
    const g = histogramSvg.append("g")
        .attr("transform", `translate(${{margin.left}},${{margin.top}})`);
    
    const fieldsData = selectedFields.map(field => {{
        const values = selectedPoints.map(i => datamap.metaData[field][i]).filter(v => v !== null);
        return {{
            field,
            distribution: createCategoricalDistribution(values, {self.max_categories}),
            color: getFieldColor(field)
        }};
    }});
    
    renderGroupedBarsInternal(g, fieldsData);
}}

function renderGroupedBarsInternal(g, fieldsData) {{
    // Get all unique categories across all fields
    const allCategories = [...new Set(fieldsData.flatMap(d => d.distribution.map(item => item.category)))];
    
    // Create map of field -> category -> count
    const dataMap = new Map();
    fieldsData.forEach(fd => {{
        const countMap = new Map(fd.distribution.map(d => [d.category, d.count]));
        dataMap.set(fd.field, countMap);
    }});
    
    // Scales
    const x0 = d3.scaleBand()
        .domain(allCategories)
        .range([0, chartWidth])
        .padding(0.2);
    
    const x1 = d3.scaleBand()
        .domain(selectedFields)
        .range([0, x0.bandwidth()])
        .padding(0.05);
    
    const maxCount = Math.max(...fieldsData.flatMap(fd => fd.distribution.map(d => d.count)));
    const y = d3.scaleLinear()
        .domain([0, maxCount])
        .range([chartHeight, 0]);
    
    // Draw grouped bars
    allCategories.forEach(category => {{
        const categoryGroup = g.append("g")
            .attr("transform", `translate(${{x0(category)}}+0)`);
        
        selectedFields.forEach(field => {{
            const count = dataMap.get(field).get(category) || 0;
            categoryGroup.append("rect")
                .attr("x", x1(field))
                .attr("y", y(count))
                .attr("width", x1.bandwidth())
                .attr("height", chartHeight - y(count))
                .attr("fill", getFieldColor(field));
        }});
    }});
    
    // Axes
    g.append("g")
        .attr("transform", `translate(0,${{chartHeight}})`)
        .call(d3.axisBottom(x0))
        .selectAll("text")
        .attr("transform", "rotate(-45)")
        .style("text-anchor", "end")
        .style("font-size", "9px");
    
    g.append("g")
        .call(d3.axisLeft(y).ticks(5))
        .selectAll("text")
        .style("font-size", "10px");
    
    // Y-axis label
    g.append("text")
        .attr("transform", "rotate(-90)")
        .attr("x", -chartHeight / 2)
        .attr("y", -35)
        .attr("text-anchor", "middle")
        .style("font-size", "11px")
        .text("Count");
}}

// Faceted mode (side-by-side for categorical)
function renderFaceted(selectedPoints) {{
    const numFields = selectedFields.length;
    const facetWidth = (chartWidth - (numFields - 1) * 10) / numFields;
    
    selectedFields.forEach((field, i) => {{
        const values = selectedPoints.map(idx => datamap.metaData[field][idx]).filter(v => v !== null);
        const distribution = createCategoricalDistribution(values, {self.max_categories});
        
        const g = histogramSvg.append("g")
            .attr("transform", `translate(${{margin.left + i * (facetWidth + 10)}},${{margin.top}})`);
        
        const x = d3.scaleBand()
            .domain(distribution.map(d => d.category))
            .range([0, facetWidth])
            .padding(0.2);
        
        const y = d3.scaleLinear()
            .domain([0, Math.max(...distribution.map(d => d.count))])
            .range([chartHeight, 0]);
        
        // Bars
        g.selectAll(".bar")
            .data(distribution)
            .enter().append("rect")
            .attr("x", d => x(d.category))
            .attr("width", x.bandwidth())
            .attr("y", d => y(d.count))
            .attr("height", d => chartHeight - y(d.count))
            .attr("fill", getFieldColor(field));
        
        // Axes
        g.append("g")
            .attr("transform", `translate(0,${{chartHeight}})`)
            .call(d3.axisBottom(x))
            .selectAll("text")
            .attr("transform", "rotate(-45)")
            .style("text-anchor", "end")
            .style("font-size", "8px");
        
        g.append("g")
            .call(d3.axisLeft(y).ticks(3))
            .selectAll("text")
            .style("font-size", "9px");
        
        // Field label
        g.append("text")
            .attr("x", facetWidth / 2)
            .attr("y", -5)
            .attr("text-anchor", "middle")
            .style("font-size", "10px")
            .style("font-weight", "bold")
            .style("fill", getFieldColor(field))
            .text(field);
    }});
}}

// ============ Legacy Render Functions (now unused) ============

// Render numeric histogram
function renderNumericHistogram(g, values) {{
    const selectionBins = createHistogramBins(values, {self.bins});
    const globalBins = {str(self.show_comparison).lower()} && globalDistribution[currentField] 
        ? globalDistribution[currentField].bins 
        : null;
    
    // Scales
    const x = d3.scaleLinear()
        .domain([selectionBins[0].x0, selectionBins[selectionBins.length - 1].x1])
        .range([0, chartWidth]);
    
    const maxCount = Math.max(
        ...selectionBins.map(d => d.count),
        ...(globalBins ? globalBins.map(d => d.count) : [0])
    );
    
    const y = d3.scaleLinear()
        .domain([0, maxCount])
        .range([chartHeight, 0]);
    
    // Global distribution (background)
    if (globalBins) {{
        g.selectAll(".bar-global")
            .data(globalBins)
            .enter().append("rect")
            .attr("class", "bar-global")
            .attr("x", d => x(d.x0))
            .attr("width", d => Math.max(0, x(d.x1) - x(d.x0) - 1))
            .attr("y", d => y(d.count))
            .attr("height", d => chartHeight - y(d.count))
            .attr("fill", "#ddd")
            .attr("opacity", 0.5);
    }}
    
    // Selection distribution
    g.selectAll(".bar-selection")
        .data(selectionBins)
        .enter().append("rect")
        .attr("class", "bar-selection")
        .attr("x", d => x(d.x0))
        .attr("width", d => Math.max(0, x(d.x1) - x(d.x0) - 1))
        .attr("y", d => y(d.count))
        .attr("height", d => chartHeight - y(d.count))
        .attr("fill", "#4CAF50");
    
    // Axes
    g.append("g")
        .attr("transform", `translate(0,${{chartHeight}})`)
        .call(d3.axisBottom(x).ticks(5))
        .selectAll("text")
        .style("font-size", "10px");
    
    g.append("g")
        .call(d3.axisLeft(y).ticks(5))
        .selectAll("text")
        .style("font-size", "10px");
    
    // Labels
    g.append("text")
        .attr("x", chartWidth / 2)
        .attr("y", chartHeight + 35)
        .attr("text-anchor", "middle")
        .style("font-size", "11px")
        .text(currentField);
    
    g.append("text")
        .attr("transform", "rotate(-90)")
        .attr("x", -chartHeight / 2)
        .attr("y", -35)
        .attr("text-anchor", "middle")
        .style("font-size", "11px")
        .text("Count");
}}

// Render categorical bar chart
function renderCategoricalChart(g, values) {{
    const selectionDist = createCategoricalDistribution(values, {self.max_categories});
    
    // Get global distribution for comparison
    let globalDist = null;
    if ({str(self.show_comparison).lower()} && globalDistribution[currentField]) {{
        globalDist = globalDistribution[currentField].distribution;
        // Create map for quick lookup
        const globalMap = new Map(globalDist.map(d => [d.category, d.count]));
        selectionDist.forEach(d => {{
            d.globalCount = globalMap.get(d.category) || 0;
        }});
    }}
    
    // Scales
    const x = d3.scaleBand()
        .domain(selectionDist.map(d => d.category))
        .range([0, chartWidth])
        .padding(0.2);
    
    const maxCount = Math.max(
        ...selectionDist.map(d => d.count),
        ...(globalDist ? selectionDist.map(d => d.globalCount || 0) : [0])
    );
    
    const y = d3.scaleLinear()
        .domain([0, maxCount])
        .range([chartHeight, 0]);
    
    // Global bars (background)
    if (globalDist) {{
        g.selectAll(".bar-global")
            .data(selectionDist)
            .enter().append("rect")
            .attr("class", "bar-global")
            .attr("x", d => x(d.category))
            .attr("width", x.bandwidth())
            .attr("y", d => y(d.globalCount || 0))
            .attr("height", d => chartHeight - y(d.globalCount || 0))
            .attr("fill", "#ddd")
            .attr("opacity", 0.5);
    }}
    
    // Selection bars
    g.selectAll(".bar-selection")
        .data(selectionDist)
        .enter().append("rect")
        .attr("class", "bar-selection")
        .attr("x", d => x(d.category))
        .attr("width", x.bandwidth())
        .attr("y", d => y(d.count))
        .attr("height", d => chartHeight - y(d.count))
        .attr("fill", "#4CAF50");
    
    // Axes
    g.append("g")
        .attr("transform", `translate(0,${{chartHeight}})`)
        .call(d3.axisBottom(x))
        .selectAll("text")
        .style("font-size", "10px")
        .attr("transform", "rotate(-45)")
        .style("text-anchor", "end");
    
    g.append("g")
        .call(d3.axisLeft(y).ticks(5))
        .selectAll("text")
        .style("font-size", "10px");
    
    // Y-axis label
    g.append("text")
        .attr("transform", "rotate(-90)")
        .attr("x", -chartHeight / 2)
        .attr("y", -35)
        .attr("text-anchor", "middle")
        .style("font-size", "11px")
        .text("Count");
}}

// Histogram callback
function histogramCallback(selectedPoints) {{
    if (!datamap.metaData) {{
        return;
    }}
    
    if (availableFields.length === 0) {{
        initializeFields();
    }}
    
    currentSelection = selectedPoints;
    
    if (selectedPoints.length === 0) {{
        histogramSvg.selectAll("*").remove();
        return;
    }}
    
    renderHistogram(selectedPoints);
}}

await datamap.addSelectionHandler(histogramCallback);

// Initialize fields on load
if (datamap.metaData) {{
    initializeFields();
    // Optionally render histogram with all points on initial load
    if ({str(self.show_comparison).lower()}) {{
        // Show global distribution if comparison is enabled
        const allPoints = Array.from({{length: datamap.metaData[currentField].length}}, (_, i) => i);
        renderHistogram(allPoints);
    }}
}}
"""
        if self.other_triggers:
            for trigger in self.other_triggers:
                result += f"""await datamap.addSelectionHandler(histogramCallback, "{trigger}");\n"""
        return result

    @property
    def css(self):
        return f"""
#histogram-container {{
    width: {self.width}px;
    padding: 12px;
    max-height: 100%;
    overflow-y: auto;
}}

.histogram-title {{
    font-weight: bold;
    font-size: 14px;
    margin-bottom: 8px;
}}

.histogram-controls {{
    display: flex;
    gap: 8px;
    margin-bottom: 8px;
    flex-wrap: wrap;
}}

.histogram-select {{
    flex: 1;
    min-width: 120px;
    padding: 4px 8px;
    border: 1px solid #ccc;
    border-radius: 4px;
    background-color: white;
    font-size: 12px;
}}

.histogram-mode-select {{
    flex: 0 0 auto;
    min-width: 130px;
    padding: 4px 8px;
    border: 1px solid #ccc;
    border-radius: 4px;
    background-color: white;
    font-size: 12px;
}}

.histogram-chips {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 10px;
}}

.histogram-chip {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 500;
    box-shadow: 0 1px 3px rgba(0,0,0,0.2);
}}

.histogram-chip span {{
    color: inherit;
}}

.chip-remove {{
    background: none;
    border: none;
    color: inherit;
    font-size: 16px;
    font-weight: bold;
    cursor: pointer;
    padding: 0;
    margin: 0;
    line-height: 1;
    opacity: 0.8;
}}

.chip-remove:hover {{
    opacity: 1;
    transform: scale(1.2);
}}

.histogram-warning {{
    padding: 6px 10px;
    background-color: #fff3cd;
    border: 1px solid #ffc107;
    border-radius: 4px;
    font-size: 11px;
    margin-bottom: 8px;
    color: #856404;
}}

.histogram-svg {{
    display: block;
}}

.histogram-svg text {{
    fill: #333;
}}

/* Dark mode support */
.darkmode .histogram-select,
body.darkmode .histogram-select,
.darkmode .histogram-mode-select,
body.darkmode .histogram-mode-select {{
    background-color: #2d2d2d;
    color: #e0e0e0;
    border-color: #555;
}}

.darkmode .histogram-warning,
body.darkmode .histogram-warning {{
    background-color: #3d3520;
    border-color: #8a6d3b;
    color: #f0e68c;
}}

.darkmode .histogram-svg text,
body.darkmode .histogram-svg text {{
    fill: #e0e0e0;
}}

.darkmode .histogram-svg .domain,
body.darkmode .histogram-svg .domain,
.darkmode .histogram-svg line,
body.darkmode .histogram-svg line {{
    stroke: #666;
}}
"""

    @property
    def html(self):
        return ""
