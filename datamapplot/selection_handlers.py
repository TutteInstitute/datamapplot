from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
import string

from datamapplot.config import ConfigManager


cfg = ConfigManager()

_DEFAULT_TAG_COLORS = [
    "#1f77b4", "#ff7f0e","#2ca02c","#d62728","#9467bd","#8c564b","#e377c2","#7f7f7f",
    "#bcbd22","#17becf","#a6008a","#656100","#8aa6ff","#007155","#ce968a","#6139f3",
    "#82b692","#ae8210","#ae9ebe","#5d5d79","#ce86ff","#398e92","#b65504","#ce31d7",
    "#758a55","#9204c6","#187100","#965982","#ef6959","#5d79ff","#7986b2","#b2a66d",
    "#5d614d","#009e71","#00a2e7","#8ea6ae","#8a9a0c","#9e7d5d","#00c66d","#246979",
    "#65c210","#865510","#a23118","#9e7dff","#9239fb","#00c2a6","#ae7d9e","#6165b2",
    "#aaa69e","#005def","#754d8e","#ce7d49","#ba5549","#f35dff","#df9600","#be4dff",
    "#55716d","#8ab65d","#6d9686","#e75500","#75616d","#4d713d","#5d8200","#9e45a6",
    "#7daed7","#867596","#5d798e","#ba75c6","#be55a2","#827135","#008641","#5d96b2",
    "#ae9ae7","#61a261","#b6756d","#5daaa6","#eb41c6","#8e9e7d","#9e8e96","#b69e10",
    "#6d49b6","#867d00","#a66d2d","#ca92c6","#6592df","#4d8265","#7d6d5d","#7d65ef",
    "#45658a","#8a8e9e","#d29a55","#b220df","#9a8e4d","#0086eb","#00829e","#969eca",
    "#c614aa","#007975","#9a86be","#5d6165","#c67100","#755939","#9a4d24","#8e3d7d",
    "#c23900","#6d7961","#eb8a69","#35baeb","#b29679","#718a8e","#9e69a2","#ae75e3",
    "#008a00","#3561ae","#8e9692","#a66549","#7d82db","#00a2b6","#24b682","#9e00aa",
    "#08ba39","#8a49ba","#75659e","#008e79","#5579c6","#927186","#558a41","#755171",
]


class SelectionHandlerBase:
    """Base class for selection handlers. Selection handlers are used to define custom behavior
    when text items are selected on the plot. This can include displaying additional information
    about the selected text items, generating visualizations based on the selected text items, or
    interacting with external APIs to process the selected text items.

    Parameters
    ----------
    dependencies : list, optional
        A list of URLs for external dependencies required by the selection handler. Default is an empty list.

    """

    def __init__(self, **kwargs):
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
    def __init__(self, n_samples=256, font_family=None, cdn_url="unpkg.com", other_triggers=None, **kwargs):
        super().__init__(
            dependencies=[
                f"https://{cdn_url}/jquery@3.7.1/dist/jquery.min.js"
            ],
            **kwargs,
        )
        self.n_samples = n_samples
        self.font_family = font_family
        self.other_triggers = other_triggers

    @property
    def javascript(self):
        result = f"""
const resampleButton = document.getElementsByClassName("resample-button")[0]
const clearSelectionButton = document.getElementsByClassName("clear-selection-button")[0]
resampleButton.onclick = resampleSelection
clearSelectionButton.onclick = clearSelection

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
    if (selectedPoints.length == 0) {{
        const selectionContainer = document.getElementById('selection-container');
        selectionContainer.style.display = 'none';
        return;       
    }}
    if (selectedPoints.length > n_samples) {{
        selectedPoints = sampleSize(selectedPoints, n_samples);
    }}
    const selectionContainer = document.getElementById('selection-container');
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
    $(selectionContainer).animate({{width:'show'}}, 500);
}}

function resampleSelection() {{
    const n_samples = {self.n_samples};
    let selectedPoints = Array.from(datamap.getSelectedIndices());
    if (selectedPoints.length > n_samples) {{
        selectedPoints = sampleSize(selectedPoints, n_samples);
    }}
    const selectionContainer = document.getElementById('selection-container');
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
    const selectionContainer = document.getElementById('selection-container');
    $(selectionContainer).animate({{width:'hide'}}, 500);

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
        position: absolute;
        top: 0;
        right: 0;
        height: 95%;
        max-width: 33%;
        z-index: 10;
        {font_family_str}
    }}
    #selection-display {{
        overflow-y: auto;
        max-height: 95%;
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
        return f"""
    <div id="selection-container" class="container-box more-opaque">
        <button class="button resample-button">Resample</button>
        <button class="button clear-selection-button"></button>
        <div id="selection-display"></div>
    </div>
        """


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
        cdn_url="unpkg.com",
        other_triggers=None,
        **kwargs,
    ):
        super().__init__(
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
        self.location = location
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
        cdn_url="unpkg.com",
        other_triggers=None,
        **kwargs,
    ):
        super().__init__(
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
        self.location = location
        self.other_triggers = other_triggers

    @property
    def javascript(self):
        result = f"""
// Stop word list
const _STOPWORDS = new Set({self.stop_words});
const cohereStackContainer = document.getElementsByClassName("stack {self.location}")[0];
const summaryLayout = document.createElement("div");
summaryLayout.id = "layout-container";
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

    def __init__(self, tag_colors=None, location="top-right", width=308, max_height="80vh", other_triggers=None, **kwargs):
        super().__init__(**kwargs)
        if tag_colors is None:
            self.tag_colors = _DEFAULT_TAG_COLORS
        else:
            self.tag_colors = tag_colors
        self.location = location
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
