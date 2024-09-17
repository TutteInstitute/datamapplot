
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
        super().__init__(dependencies=["https://ajax.googleapis.com/ajax/libs/jquery/3.7.1/jquery.min.js"], **kwargs)
        self.n_samples = n_samples
        self.font_family = "Roboto, sans-serif" if font_family is None else font_family

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
    let selectedPoints = Array.from(dataSelectionManager.getSelectedIndices());
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
        return f"""
    #selection-container {{
        display: none;
        position: absolute;
        top: 0;
        right: 0;
        height: 95%;
        max-width: 33%;
        z-index: 10;
        font-family: {self.font_family};
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