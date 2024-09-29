from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
import string


class SelectionHandlerBase:

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

    def __init__(self, n_samples=256, font_family=None, **kwargs):
        super().__init__(
            dependencies=[
                "https://ajax.googleapis.com/ajax/libs/jquery/3.7.1/jquery.min.js"
            ],
            **kwargs,
        )
        self.n_samples = n_samples
        self.font_family = font_family

    @property
    def javascript(self):
        return f"""
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

function lassoSelectionCallback(selectedPoints) {{
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
        """

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
    <div id="selection-container" class="container-box">
        <button class="button resample-button">Resample</button>
        <button class="button clear-selection-button"></button>
        <div id="selection-display"></div>
    </div>
        """


class WordCloud(SelectionHandlerBase):

    def __init__(
        self,
        n_words=256,
        width=500,
        height=500,
        font_family=None,
        stop_words=None,
        n_rotations=0,
        color_scale="YlGnBu",
        location=("bottom", "right"),
        **kwargs,
    ):
        super().__init__(
            dependencies=[
                "https://d3js.org/d3.v6.min.js",
                "https://unpkg.com/d3-cloud@1.2.7/build/d3.layout.cloud.js",
                "https://ajax.googleapis.com/ajax/libs/jquery/3.7.1/jquery.min.js",
            ],
            **kwargs,
        )
        self.n_words = n_words
        self.width = width
        self.height = height
        self.font_family = font_family
        self.stop_words = stop_words or list(ENGLISH_STOP_WORDS)
        self.n_rotations = min(22, n_rotations)
        self.location = location
        if color_scale.endswith("_r"):
            self.color_scale = string.capwords(color_scale[:1]) + color_scale[1:-2]
            self.color_scale_reversed = True
        else:
            self.color_scale = string.capwords(color_scale[:1]) + color_scale[1:]
            self.color_scale_reversed = False

    @property
    def javascript(self):
        return f"""
const _STOPWORDS = new Set({self.stop_words});
const _ROTATIONS = [0, -90, 90, -45, 45, -30, 30, -60, 60, -15, 15, -75, 75, -7.5, 7.5, -22.5, 22.5, -52.5, 52.5, -37.5, 37.5, -67.5, 67.5];
const wordCloudSvg = d3.select("#word-cloud").append("svg")
    .attr("width", {self.width})
    .attr("height", {self.height})
    .append("g")
    .attr("transform", "translate(" + {self.width} / 2 + "," + {self.height} / 2 + ")");
const wordCloudItem = document.getElementById("word-cloud");

function wordCounter(textItems) {{
    const words = textItems.join(' ').toLowerCase().split(/\s+/);
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
    const t = d3.transition().duration(500);
    
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

function lassoSelectionCallback(selectedPoints) {{
    if (selectedPoints.length > 0) {{
        $(wordCloudItem).animate({{height:'show'}}, 250);
    }} else {{
        $(wordCloudItem).animate({{height:'hide'}}, 250);
    }}
    let selectedText;
    if (datamap.metaData) {{
        selectedText = selectedPoints.map(i => datamap.metaData.hover_text[i]);
    }} else {{
        selectedText = ["Meta data still loading ..."];
    }}
    const wordCounts = wordCounter(selectedText);
    generateWordCloud(wordCounts);
}}
"""

    @property
    def html(self):
        return """<div id="word-cloud" class="container-box"></div>"""

    @property
    def css(self):
        return f"""
#word-cloud {{
    position: absolute;
    {self.location[1]}: 0;
    {self.location[0]}: 0;
    display: none;
    width: {self.width}px;
    height: {self.height}px;
    z-index: 10;
}}
"""


class TagSelection(SelectionHandlerBase):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def javascript(self):
        return f"""
    const tags = new Map();
    const tagButton = document.getElementsByClassName("tag-button")[0]
    tagButton.onclick = createNewTag();

    function lassoSelectionCallback(selectedPoints) {{
        if (selectedPoints.length == 0) {{
            tagButton.classList.add("enabled");
        }} else {{
            tagButton.classList.add("enabled");
        }}
    }}
        """

    @property
    def html(self):
        return f"""
    <div id="tag-container">
        <div id="tag-display">
        </div>
        <span>
            <button class="button tag-button">Create New Tag</button>
            <input type="text" id="tag-input" placeholder="Enter tag name">
        </span>
    </div>
        """
