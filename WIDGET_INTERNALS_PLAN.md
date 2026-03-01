# Widget Internals Connection Plan

## Implementation Status

### ✅ Phase 1: Widget-Owned JavaScript Initialization (COMPLETE)
- All 7 widgets have `javascript` property implementations
- All 7 widgets have `dependencies` class variable declarations
- Self-initialization pattern established using IIFEs with `datamapReady` event
- Modified files: `datamapplot/widgets.py`

### ✅ Phase 2: Data Flow - Widget to Template Context (COMPLETE)
- Created `collect_widget_data()` function to extract data from widget instances
- Created `encode_widget_data()` function to prepare data for template embedding
- Integrated data collection into rendering pipeline in `interactive_rendering.py`
- Added widget data exposure in template `data_setup.js.jinja2`
- Widget data flows: widgets → collect → encode → template context → window.widgetHistogramData/widgetColormapData
- Modified files: `datamapplot/widget_helpers.py`, `datamapplot/interactive_rendering.py`, `datamapplot/templates/data_setup.js.jinja2`

### 🔲 Phase 3: Template Refactoring (PENDING)
- Remove flag-based conditionals from templates
- Use widget-driven rendering instead of `{% if enable_* %}` blocks

### 🔲 Phase 4: Testing (PENDING)
- Test all 7 widget types
- Verify functional equivalence with legacy system

### 🔲 Phase 5-7: Additional Phases (PENDING)
- See detailed phase descriptions below

---

## Problem Statement

Currently, the widget system (`use_widgets=True`) has a fundamental disconnection between widget class instances and their actual functionality:

1. **Widget classes just render empty containers** - `TopicTreeWidget.html` returns `<div id="topic-tree-container"></div>` but doesn't ensure the TopicTree JS class is instantiated
2. **Data isn't connected** - `HistogramWidget` accepts `histogram_data` but this data isn't passed to the rendering pipeline
3. **JavaScript initialization is decoupled** - The JS code that creates `new TopicTree(...)` is in Jinja2 templates controlled by `{% if enable_topic_tree %}` flags, not by widget presence
4. **Legacy bridge is incomplete** - `legacy_widget_flags_from_widgets()` extracts widget parameters but the actual instantiation logic still lives in templates

## Current Architecture

### Widget System Flow (use_widgets=True)
```
Widget classes (widgets.py)
  ↓ .html property
Empty container divs
  ↓ grouped by location
Template rendering
  ↓ BUT...
JS initialization depends on enable_* flags (NOT widget presence)
  ↓ Result: empty containers, no JS components
```

### Legacy System Flow (use_widgets=False)
```
enable_topic_tree=True parameter
  ↓
Jinja2 template: {% if enable_topic_tree %}
  ↓
JS code: new TopicTree(document.querySelector('#topic-tree'), ...)
  ↓ WORKS
Fully initialized component
```

## Root Cause Analysis

### Widget Type Analysis

Before diving into solutions, let's catalog all 7 widget types and their specific requirements:

| Widget Type | Needs JS Init? | Needs External Data? | Dependencies | Complexity |
|-------------|----------------|---------------------|--------------|------------|
| **TitleWidget** | ❌ No | ❌ No | None | Simple - Pure HTML/CSS |
| **LogoWidget** | ❌ No | ❌ No | None | Simple - Pure HTML/CSS |
| **SearchWidget** | ✅ Minimal | ❌ No | datamap.js | Medium - DOM event wiring |
| **LegendWidget** | ✅ Yes | ✅ Dynamic | datamap.js | Medium - Dynamic updates |
| **ColormapSelectorWidget** | ✅ Yes | ✅ Yes (colormap list) | colormap_selector.js/css | High - Interactive UI |
| **TopicTreeWidget** | ✅ Yes | ✅ Yes (label data) | topic_tree.js/css | High - Complex JS component |
| **HistogramWidget** | ✅ Yes | ✅ Yes (histogram array) | d3.js, d3_histogram.js/css | High - Data viz + interactions |

**Key insights:**
- **2 widgets are pure HTML/CSS** (Title, Logo) - already work perfectly
- **2 widgets need minimal JS** (Search, Legend) - configure existing DataMap functionality
- **3 widgets need full JS initialization** (Colormap, TopicTree, Histogram) - instantiate JS classes
- **3 widgets need external data** (Histogram array, Colormap list, Label data)

### 1. Templates Use Flags, Not Widget-Driven Logic

**File: `templates/data_loaders.js.jinja2`**
```jinja
{% if enable_topic_tree %}
function setupTopicTree(labelData) {
  const topicTreeContainer = document.querySelector('#topic-tree');
  const topicTree = new TopicTree(
    topicTreeContainer,
    datamap,
    ...
  );
}
{% endif %}
```

The template checks `enable_topic_tree` flag, not "is there a TopicTreeWidget in the page?"

### 2. Widget Classes Don't Generate Their JS Initialization

**File: `widgets.py` - TopicTreeWidget**
```python
@property
def html(self):
    return f'<div id="{self.get_container_id()}" class="container-box"></div>'
    
# Missing: @property def javascript(self):
#   return JS code to instantiate TopicTree with this widget's parameters
```

The widget knows its parameters but doesn't emit the JS to use them.

### 3. Data Flow is Disconnected

**Example: HistogramWidget**
```python
def __init__(self, histogram_data=None, ...):
    self.histogram_data = histogram_data  # Stored but not used!
```

The data sits on the widget instance but never makes it to:
- The template context
- The JS that creates the histogram
- The data encoding pipeline

### 4. Bridge Function is Incomplete

**File: `widget_helpers.py`**
```python
def legacy_widget_flags_from_widgets(widgets):
    enable_topic_tree = any(isinstance(w, TopicTreeWidget) for w in widgets)
    topic_tree_kwds = {...}  # Extract params
    return enable_topic_tree, ...
```

This sets `enable_topic_tree=True` which makes templates render the JS, but:
- It's still using template conditionals, not widget-driven rendering
- Widget-specific container IDs may not match legacy assumptions
- Multiple instances of same widget type aren't handled

## Solution Architecture

### Phase 1: Widget-Owned JavaScript Initialization

**Make each widget responsible for its own JS initialization code**

Below are detailed examples showing how each widget type will implement self-initialization:

#### 1. TopicTreeWidget - Complex JS Component
```python
class TopicTreeWidget(WidgetBase):
    @property
    def javascript(self):
        """Generate JS to instantiate this specific widget instance."""
        container_id = self.get_container_id()
        
        button_click = self.button_on_click if self.button_on_click else 'null'
        
        return f"""
        (function() {{
            const container = document.querySelector('#{container_id}');
            if (!container || !window.datamap) return;
            
            function setup() {{
                const topicTree = new TopicTree(
                    container,
                    window.datamap,
                    {str(self.button_on_click is not None).lower()},
                    {json.dumps(self.button_icon)},
                    {{
                        title: {json.dumps(self.tree_title)},
                        maxWidth: {json.dumps(self.max_width)},
                        maxHeight: {json.dumps(self.max_height)},
                        fontSize: {json.dumps(self.font_size)},
                        colorBullets: {str(self.color_bullets).lower()},
                    }}
                );
                
                {self._generate_button_handlers() if self.button_on_click else ''}
                
                // Set up viewport highlighting
                const debounced = debounce(({{viewState, interactionState}}) => {{
                    const userIsInteracting = Object.values(interactionState).every(Boolean);
                    if (!userIsInteracting) {{
                        const visible = getVisibleTextData(viewState, window.datamap.labelData);
                        if (visible) topicTree.highlightElements(visible);
                    }}
                }}, 150);
                
                window.datamap.deckgl.setProps({{
                    onViewStateChange: debounced,
                }});
                
                // Store reference
                window.datamap.widgets = window.datamap.widgets || {{}};
                window.datamap.widgets['{self.widget_id}'] = topicTree;
            }}
            
            // Run after data is loaded
            if (window.datamap && window.datamap.labelData) {{
                setup();
            }} else {{
                document.addEventListener('datamapDataLoaded', setup);
            }}
        }})();
        """
```

#### 2. HistogramWidget - Needs External Data
```python
class HistogramWidget(WidgetBase):
    @property
    def javascript(self):
        """Generate JS to instantiate histogram with data."""
        container_id = self.get_container_id()
        widget_id = self.widget_id
        
        return f"""
        (function() {{
            const container = document.querySelector('#{container_id}');
            if (!container) return;
            
            function setup() {{
                // Get data for THIS widget instance
                const histData = window.widgetHistogramData?.['{widget_id}'];
                if (!histData) {{
                    console.warn('No histogram data for widget {widget_id}');
                    return;
                }}
                
                const histogram = new D3Histogram(
                    container,
                    histData,
                    window.datamap,
                    {{
                        width: {self.histogram_width},
                        height: {self.histogram_height},
                        title: {json.dumps(self.histogram_title)},
                        binCount: {self.histogram_bin_count},
                        binFillColor: {json.dumps(self.histogram_bin_fill_color)},
                        binSelectedFillColor: {json.dumps(self.histogram_bin_selected_fill_color)},
                        binUnselectedFillColor: {json.dumps(self.histogram_bin_unselected_fill_color)},
                        binContextFillColor: {json.dumps(self.histogram_bin_context_fill_color)},
                        logScale: {str(self.histogram_log_scale).lower()},
                    }}
                );
                
                // Store reference
                window.datamap.widgets = window.datamap.widgets || {{}};
                window.datamap.widgets['{widget_id}'] = histogram;
            }}
            
            if (window.datamap && window.datamap.pointData) {{
                setup();
            }} else {{
                document.addEventListener('datamapDataLoaded', setup);
            }}
        }})();
        """
```

#### 3. SearchWidget - DOM Event Handling
```python
class SearchWidget(WidgetBase):
    @property
    def javascript(self):
        """Generate JS for search functionality."""
        # Search uses the DataMap's built-in search by ID
        # Just need to ensure datamap knows about this search input
        return f"""
        (function() {{
            const searchInput = document.querySelector('#text-search');
            if (!searchInput || !window.datamap) return;
            
            function initSearch() {{
                // DataMap's constructor already sets up search on 'text-search' ID
                // But we ensure the search field is set correctly
                if (window.datamap.searchField !== {json.dumps(self.search_field)}) {{
                    window.datamap.searchField = {json.dumps(self.search_field)};
                    console.log('Search widget configured for field:', window.datamap.searchField);
                }}
            }}
            
            if (window.datamap) {{
                initSearch();
            }} else {{
                document.addEventListener('datamapReady', initSearch);
            }}
        }})();
        """
```

#### 4. ColormapSelectorWidget - Interactive UI
```python
class ColormapSelectorWidget(WidgetBase):
    @property
    def javascript(self):
        """Generate JS for colormap selector."""
        container_id = self.get_container_id()
        widget_id = self.widget_id
        
        return f"""
        (function() {{
            const container = document.querySelector('#{container_id}');
            if (!container || !window.datamap) return;
            
            function setup() {{
                const colormaps = window.widgetColormapData?.['{widget_id}'] || [];
                if (colormaps.length === 0) {{
                    console.warn('No colormaps provided for widget {widget_id}');
                    return;
                }}
                
                const selector = new ColormapSelector(
                    container,
                    window.datamap,
                    colormaps
                );
                
                // Store reference
                window.datamap.widgets = window.datamap.widgets || {{}};
                window.datamap.widgets['{widget_id}'] = selector;
            }}
            
            if (window.datamap) {{
                setup();
            }} else {{
                document.addEventListener('datamapReady', setup);
            }}
        }})();
        """
```

#### 5. LegendWidget - Dynamic Content
```python
class LegendWidget(WidgetBase):
    @property
    def javascript(self):
        """Generate JS for legend (shown/hidden dynamically)."""
        container_id = self.get_container_id()
        widget_id = self.widget_id
        
        return f"""
        (function() {{
            const container = document.querySelector('#{container_id}');
            if (!container || !window.datamap) return;
            
            function setup() {{
                // Legend visibility is controlled by datamap
                // When colormap changes, legend updates
                window.datamap.legendContainer = container;
                
                // Initial setup
                if (window.datamap.currentColormap) {{
                    window.datamap.updateLegend();
                }}
                
                // Store reference
                window.datamap.widgets = window.datamap.widgets || {{}};
                window.datamap.widgets['{widget_id}'] = {{
                    container: container,
                    show: () => container.style.display = 'block',
                    hide: () => container.style.display = 'none',
                }};
            }}
            
            if (window.datamap) {{
                setup();
            }} else {{
                document.addEventListener('datamapReady', setup);
            }}
        }})();
        """
```

#### 6. TitleWidget - Pure HTML (No JS Needed)
```python
class TitleWidget(WidgetBase):
    @property
    def javascript(self):
        """Title widget needs no JavaScript initialization."""
        return ""  # Pure HTML/CSS widget
```

#### 7. LogoWidget - Pure HTML (No JS Needed)
```python
class LogoWidget(WidgetBase):
    @property
    def javascript(self):
        """Logo widget needs no JavaScript initialization."""
        return ""  # Pure HTML/CSS widget
```

**Key changes:**
- Each widget generates its own complete initialization code
- Widgets use their own container IDs (handles multiple instances)
- Widgets wait for appropriate data/events before initializing
- Some widgets need external data (histograms), others are self-contained
- Pure HTML widgets (title, logo) return empty string for JS
- All JS widgets store references in `window.datamap.widgets[widget_id]`

### Phase 2: Data Flow - Widget to Template Context

**Create a data collection system for all widget types**

```python
# In widget_helpers.py
def collect_widget_data(widgets):
    """Extract data that needs to be encoded/embedded from widgets."""
    widget_data = {
        'histograms': [],
        'colormaps': [],
        'search_fields': [],
        # Other widget types don't need data
    }
    
    for widget in widgets:
        # HistogramWidget: needs external data array
        if isinstance(widget, HistogramWidget) and widget.histogram_data is not None:
            widget_data['histograms'].append({
                'widget_id': widget.widget_id,
                'data': widget.histogram_data,
                'settings': {
                    'width': widget.histogram_width,
                    'height': widget.histogram_height,
                    'title': widget.histogram_title,
                    'bin_count': widget.histogram_bin_count,
                    'bin_fill_color': widget.histogram_bin_fill_color,
                    'bin_selected_fill_color': widget.histogram_bin_selected_fill_color,
                    'bin_unselected_fill_color': widget.histogram_bin_unselected_fill_color,
                    'bin_context_fill_color': widget.histogram_bin_context_fill_color,
                    'log_scale': widget.histogram_log_scale,
                }
            })
        
        # ColormapSelectorWidget: needs colormap list
        elif isinstance(widget, ColormapSelectorWidget):
            widget_data['colormaps'].append({
                'widget_id': widget.widget_id,
                'available_colormaps': widget.available_colormaps,
            })
        
        # SearchWidget: needs to configure search field
        elif isinstance(widget, SearchWidget):
            widget_data['search_fields'].append({
                'widget_id': widget.widget_id,
                'search_field': widget.search_field,
            })
        
        # TopicTreeWidget: uses label data already in datamap (no extra data)
        # LegendWidget: dynamically populated (no extra data)
        # TitleWidget: pure HTML (no data)
        # LogoWidget: pure HTML (no data)
    
    return widget_data


def encode_widget_data(widget_data, point_data_length):
    """Encode widget data for embedding in HTML."""
    encoded = {}
    
    # Encode histogram data
    if widget_data['histograms']:
        encoded['histograms'] = {}
        for hist in widget_data['histograms']:
            # Validate data length matches point data
            if len(hist['data']) != point_data_length:
                raise ValueError(
                    f"Histogram data for widget '{hist['widget_id']}' has "
                    f"{len(hist['data'])} elements but point data has "
                    f"{point_data_length} points"
                )
            
            # Use existing encoding functions
            encoded_data = encode_histogram_data(hist['data'])
            encoded['histograms'][hist['widget_id']] = {
                'data': encoded_data,
                'settings': hist['settings'],
            }
    
    # Colormaps don't need encoding (just JSON)
    if widget_data['colormaps']:
        encoded['colormaps'] = {
            cm['widget_id']: cm['available_colormaps']
            for cm in widget_data['colormaps']
        }
    
    # Search fields are simple strings
    if widget_data['search_fields']:
        # Use the first search field found (typically only one)
        encoded['search_field'] = widget_data['search_fields'][0]['search_field']
    
    return encoded
```

**In rendering pipeline:**
```python
# interactive_rendering.py
if use_widget_system:
    # Collect data from widgets
    widget_data = collect_widget_data(all_widgets)
    
    # Encode data for embedding
    encoded_widget_data = encode_widget_data(widget_data, len(point_data))
    
    # Pass to template
    template_context['widget_data'] = encoded_widget_data
```

### Phase 3: Template Refactoring

**Remove flag-based conditionals, use widget-driven rendering**

**Old approach (data_loaders.js.jinja2):**
```jinja
{% if enable_topic_tree %}
function setupTopicTree(labelData) { ... }
{% endif %}
```

**New approach:**
```jinja
// Widget initialization scripts are injected by widgets themselves
// No need for conditional blocks here

// Data loading still happens centrally
{% if widget_data and widget_data.histograms %}
window.widgetHistogramData = {
  {% for hist in widget_data.histograms %}
  "{{ hist.widget_id }}": {{ hist.encoded }},
  {% endfor %}
};
{% endif %}
```

### Phase 4: Widget-Specific Data Access

**Each widget type accesses its data differently at runtime**

```python
class HistogramWidget(WidgetBase):
    dependencies = ["js:d3", "js:histogram", "css:histogram"]
    
    @property
    def javascript(self):
        # Needs external data passed via window.widgetHistogramData
        return f"""
        (function() {{
            const histData = window.widgetHistogramData?.['{self.widget_id}'];
            if (!histData) {{
                console.warn('No histogram data for {self.widget_id}');
                return;
            }}
            // ... create histogram with histData
        }})();
        """


class TopicTreeWidget(WidgetBase):
    dependencies = ["js:topic_tree", "css:topic_tree"]
    
    @property
    def javascript(self):
        # Uses label data already available in window.datamap.labelData
        return f"""
        (function() {{
            if (!window.datamap?.labelData) return;
            const topicTree = new TopicTree(
                document.querySelector('#{self.get_container_id()}'),
                window.datamap,
                // ... uses datamap.labelData internally
            );
        }})();
        """


class SearchWidget(WidgetBase):
    dependencies = []  # Search uses datamap.js (always loaded)
    
    @property
    def javascript(self):
        # Configures DataMap's search functionality
        return f"""
        (function() {{
            if (window.datamap) {{
                window.datamap.searchField = {json.dumps(self.search_field)};
            }}
        }})();
        """


class ColormapSelectorWidget(WidgetBase):
    dependencies = ["js:colormap_selector", "css:colormap_selector"]
    
    @property
    def javascript(self):
        # Needs colormap list passed via window.widgetColormapData
        return f"""
        (function() {{
            const colormaps = window.widgetColormapData?.['{self.widget_id}'];
            if (!colormaps) return;
            new ColormapSelector(
                document.querySelector('#{self.get_container_id()}'),
                window.datamap,
                colormaps
            );
        }})();
        """


class LegendWidget(WidgetBase):
    dependencies = []  # Legend uses datamap.js (always loaded)
    
    @property
    def javascript(self):
        # Registers container with datamap for dynamic updates
        return f"""
        (function() {{
            if (window.datamap) {{
                window.datamap.legendContainer = document.querySelector('#{self.get_container_id()}');
                window.datamap.updateLegend?.();
            }}
        }})();
        """


class TitleWidget(WidgetBase):
    dependencies = []  # Pure HTML
    
    @property
    def javascript(self):
        return ""  # No JavaScript needed


class LogoWidget(WidgetBase):
    dependencies = []  # Pure HTML
    
    @property
    def javascript(self):
        return ""  # No JavaScript needed
```

**Summary of widget data requirements:**

| Widget | Data Source | Data Format | When Available |
|--------|-------------|-------------|----------------|
| HistogramWidget | External array | `window.widgetHistogramData[id]` | After data loaded |
| ColormapSelectorWidget | Colormap list | `window.widgetColormapData[id]` | Immediate |
| SearchWidget | Configuration | Direct DataMap property | Immediate |
| TopicTreeWidget | Label data | `window.datamap.labelData` | After data loaded |
| LegendWidget | Dynamic | `window.datamap` methods | After colormap set |
| TitleWidget | None | N/A | N/A |
| LogoWidget | None | N/A | N/A |

### Phase 5: Dependency Management

**Each widget declares what JS/CSS files it needs**

```python
class WidgetBase:
    """Base class with dependency system."""
    
    # Class-level dependencies (can be overridden by instances)
    dependencies = []
    
    def get_dependencies(self):
        """Get list of dependencies for this widget."""
        return self.dependencies


# Widget dependency declarations
class TopicTreeWidget(WidgetBase):
    dependencies = ["js:topic_tree", "css:topic_tree"]

class HistogramWidget(WidgetBase):
    dependencies = ["js:d3", "js:histogram", "css:histogram"]

class ColormapSelectorWidget(WidgetBase):
    dependencies = ["js:colormap_selector", "css:colormap_selector"]

class LegendWidget(WidgetBase):
    dependencies = []  # Uses datamap.js (always loaded)

class SearchWidget(WidgetBase):
    dependencies = []  # Uses datamap.js (always loaded)

class TitleWidget(WidgetBase):
    dependencies = []  # Pure HTML/CSS

class LogoWidget(WidgetBase):
    dependencies = []  # Pure HTML/CSS


# In widget_helpers.py
def collect_widget_dependencies(widgets):
    """Collect all unique dependencies from widgets."""
    deps = {
        'js_files': set(),
        'css_files': set(),
        'external_js': set(),
    }
    
    for widget in widgets:
        for dep in widget.get_dependencies():
            if ':' not in dep:
                continue
                
            dep_type, dep_name = dep.split(':', 1)
            
            if dep_name.startswith('http'):
                deps['external_js'].add(dep_name)
            elif dep_type == 'js':
                deps['js_files'].add(dep_name)
            elif dep_type == 'css':
                deps['css_files'].add(dep_name)
    
    return deps


# Map of dependency names to file paths
DEPENDENCY_FILES = {
    'js': {
        'd3': 'https://cdn.jsdelivr.net/npm/d3@7',  # External CDN
        'histogram': 'static/js/d3_histogram.js',
        'topic_tree': 'static/js/topic_tree.js',
        'colormap_selector': 'static/js/colormap_selector.js',
        'lasso_selection': 'static/js/lasso_selection.js',
        'quad_tree': 'static/js/quad_tree.js',
        'drawer': 'static/js/drawer.js',
    },
    'css': {
        'histogram': 'static/css/histogram.css',
        'topic_tree': 'static/css/topic_tree.css',
        'colormap_selector': 'static/css/colormap_selector.css',
        'drawer': 'static/css/drawer_style.css',
    }
}


# In rendering
def get_js_dependency_sources_from_widgets(widgets, minify=False):
    """Get JS dependencies based on widget requirements."""
    widget_deps = collect_widget_dependencies(widgets)
    
    js_sources = {}
    static_dir = Path(__file__).resolve().parent / "static" / "js"
    
    # Always include core datamap files
    for core_file in ["datamap.js", "data_selection_manager.js"]:
        with open(static_dir / core_file, "r", encoding="utf-8") as f:
            content = f.read()
            js_sources[core_file] = jsmin(content) if minify else content
    
    # Include widget-specific files
    for dep_name in widget_deps['js_files']:
        if dep_name in DEPENDENCY_FILES['js']:
            file_path = DEPENDENCY_FILES['js'][dep_name]
            if not file_path.startswith('http'):
                with open(static_dir / Path(file_path).name, "r") as f:
                    content = f.read()
                    js_sources[dep_name] = jsmin(content) if minify else content
    
    return js_sources, widget_deps['external_js']
```

**Dependency loading priority:**
1. Core DataMap files (always loaded)
2. Widget-specific JS files (based on widget presence)
3. Widget-specific CSS files (based on widget presence)
4. External CDN libraries (D3, etc.)

## Implementation Checklist

### Step 1: Make Widgets Self-Initializing (Per Widget Type)
- [ ] **TitleWidget**: No changes needed (already pure HTML)
- [ ] **LogoWidget**: No changes needed (already pure HTML)
- [ ] **SearchWidget**: Add `javascript` property that configures datamap.searchField
- [ ] **LegendWidget**: Add `javascript` property that registers container with datamap
- [ ] **ColormapSelectorWidget**: Add `javascript` property that instantiates ColormapSelector
- [ ] **TopicTreeWidget**: Add `javascript` property that instantiates TopicTree with event wiring
- [ ] **HistogramWidget**: Add `javascript` property that instantiates D3Histogram with data
- [ ] Test: Each widget's JS can instantiate its component correctly

### Step 2: Connect Widget Data to Rendering Pipeline
- [ ] Create `collect_widget_data()` function
- [ ] Handle **HistogramWidget** data encoding (array → base64)
- [ ] Handle **ColormapSelectorWidget** colormap list (JSON)
- [ ] Handle **SearchWidget** field configuration (string)
- [ ] **TopicTreeWidget** uses existing label data (no extra data)
- [ ] **LegendWidget** is dynamically populated (no extra data)
- [ ] Pass widget data to template context as `widget_data`
- [ ] Test: Data flows from each widget type → template → JS

### Step 3: Refactor Templates
- [ ] Remove `{% if enable_topic_tree %}` conditionals from data_loaders.js.jinja2
- [ ] Remove `{% if enable_histogram %}` conditionals
- [ ] Remove `{% if enable_colormap_selector %}` conditionals
- [ ] Create data exposure blocks for:
  - `window.widgetHistogramData` (if any HistogramWidgets)
  - `window.widgetColormapData` (if any ColormapSelectorWidgets)
- [ ] Move JS class definitions to always-included files (not conditional)
- [ ] Test: Templates work with widget system

### Step 4: Update Dependency System (Per Widget Type)
- [ ] Add `dependencies = []` to **TitleWidget**
- [ ] Add `dependencies = []` to **LogoWidget**
- [ ] Add `dependencies = []` to **SearchWidget** (uses core datamap.js)
- [ ] Add `dependencies = []` to **LegendWidget** (uses core datamap.js)
- [ ] Add `dependencies = ["js:colormap_selector", "css:colormap_selector"]` to **ColormapSelectorWidget**
- [ ] Add `dependencies = ["js:topic_tree", "css:topic_tree"]` to **TopicTreeWidget**
- [ ] Add `dependencies = ["js:d3", "js:histogram", "css:histogram"]` to **HistogramWidget**
- [ ] Update `collect_widget_dependencies()` to aggregate from all widgets
- [ ] Update `get_js_dependency_urls()` to load based on widget deps
- [ ] Test: Correct JS/CSS files are loaded for each widget type

### Step 5: Handle Legacy → Widget Bridge
- [ ] Keep `legacy_widget_flags_from_widgets()` for transition period
- [ ] Extract settings from all 7 widget types:
  - Title/subtitle from **TitleWidget**
  - Logo from **LogoWidget**
  - Search field from **SearchWidget**
  - Histogram data from **HistogramWidget**
  - Topic tree options from **TopicTreeWidget**
  - Colormap list from **ColormapSelectorWidget**
  - Legend settings from **LegendWidget**
- [ ] Ensure flags needed for template compatibility are set
- [ ] Test: Both paths work identically for all widget types

### Step 6: Multiple Instance Support
- [ ] Test multiple **HistogramWidgets** (different data each)
- [ ] Test multiple **SearchWidgets** (corner + drawer)
- [ ] Test multiple **TopicTreeWidgets** (complex - may need design decision)
- [ ] Test multiple **ColormapSelectorWidgets** (complex - may conflict)
- [ ] **TitleWidget**: Multiple instances should work fine
- [ ] **LogoWidget**: Multiple instances should work fine
- [ ] **LegendWidget**: Typically only one needed
- [ ] Document limitations/best practices per widget type

### Step 7: Documentation & Examples
- [ ] Update widget documentation to show data flow for each type
- [ ] Add example: **HistogramWidget** with custom date data
- [ ] Add example: **TopicTreeWidget** with custom button actions
- [ ] Add example: **ColormapSelectorWidget** with custom palettes
- [ ] Add example: Mixed layout with all 7 widget types
- [ ] Document which widgets can have multiple instances
- [ ] Document JavaScript API for accessing `window.datamap.widgets[id]`

## Backward Compatibility Strategy

**During Transition:**
1. Keep `enable_*` parameters working via legacy system
2. When `use_widgets=True`, still set enable flags via `legacy_widget_flags_from_widgets()`
3. Templates use `{% if enable_topic_tree or widget_has_topic_tree %}`
4. Gradually migrate examples to widget system

**After Full Migration:**
1. Deprecate `enable_*` parameters (keep with warnings)
2. Remove flag-based conditionals from templates
3. Templates driven purely by widget presence
4. Remove `legacy_widget_flags_from_widgets()`

## Testing Strategy

### Unit Tests
- Widget JS generation produces valid code
- Data collection extracts correct data from widgets
- Dependency collection aggregates correctly

### Integration Tests
- HistogramWidget with data renders functional histogram
- TopicTreeWidget creates interactive tree
- Multiple widgets of same type coexist
- Widget data survives encoding/decoding

### Regression Tests
- Legacy system (`use_widgets=False`) still works identically
- Mixed mode (some legacy params + some widgets) works
- All existing examples still work

## Open Questions

### 1. Multi-instance Semantics (Per Widget Type)

**TitleWidget**: ✅ Multiple instances make sense (different corners could have different titles)

**LogoWidget**: ✅ Multiple logos could be useful (sponsor logos, etc.)

**SearchWidget**: ⚠️ Multiple search boxes possible but need to clarify behavior:
- Should they all search the same field?
- Should they have independent state or sync?
- Current: DataMap expects one `#text-search` ID

**LegendWidget**: ⚠️ Typically only one legend is needed:
- Multiple legends for different layers could make sense
- But DataMap currently assumes one legend container
- Need to design multi-legend support or limit to one

**ColormapSelectorWidget**: ⚠️ Multiple selectors are complex:
- They would all control the same datamap colormap
- Could conflict if used simultaneously
- Recommendation: Limit to one instance

**TopicTreeWidget**: ⚠️ Multiple trees are complex:
- Each tree needs different label layers?
- Or same data with different visualizations?
- Need to clarify use case before implementing

**HistogramWidget**: ✅ Multiple histograms make perfect sense:
- Different temporal views (year, month, day)
- Different metadata dimensions
- Each histogram has independent data and selection

### 2. Data Dependencies & Validation

**HistogramWidget**: 
- Q: Should histogram_data length be validated at widget creation or render time?
- Q: What if histogram_data is None? Show empty histogram or hide widget?
- A: Validate at render time, warn if None, allow empty for dynamic updates

**ColormapSelectorWidget**:
- Q: What if available_colormaps is empty?
- A: Log warning, widget should gracefully degrade

**TopicTreeWidget**:
- Q: What if labelData isn't hierarchical?
- A: TopicTree.js should handle flat structures (current behavior)

### 3. Dynamic Updates

Should widgets support updating their data after creation?

**Use cases:**
- `histogram_widget.update_data(new_dates)` for dynamic filtering
- `colormap_widget.set_colormaps(new_list)` for theme changes
- `legend_widget.refresh()` after colormap change

**Recommendation:** Start with static initialization, add dynamic updates as Phase 2

### 4. Widget Communication

Should widgets be able to communicate with each other?

**Examples:**
- SearchWidget highlights results → TopicTreeWidget expands matching nodes
- HistogramWidget selection → LegendWidget updates visible categories
- ColormapSelectorWidget changes → LegendWidget updates colors

**Current approach:** Communication through `window.datamap` (central hub)
- Widgets register with datamap
- Events flow through datamap's selection system
- Already works for basic interactions

**Recommendation:** Keep datamap as central communication hub, no direct widget-to-widget communication

### 5. Lazy Loading for Drawer Widgets

Should widget JS/data be loaded only when drawer opens for the first time?

**Pros:**
- Faster initial page load
- Less memory for unused widgets
- Better for mobile

**Cons:**
- More complex initialization logic
- First drawer open has delay
- Hard to implement with current template system

**Recommendation:** Load all widget JS/CSS upfront (current approach), defer expensive computations only

### 6. Widget-Specific Container IDs

**Current:** Each widget instance has unique container ID via `get_container_id()`
- Format: `{widget_id}-container`
- Works for multiple instances if widget_id is unique

**Question:** Should users be able to customize widget_id?
- Yes - already supported via `widget_id` parameter
- Need to document this as the way to have multiple instances

**Recommendation:** Document that unique `widget_id` is required for multiple instances of same type

## Success Criteria

When this implementation is complete, all 7 widget types should work perfectly:

### Per-Widget Success Criteria

**TitleWidget:**
- ✅ Creating `TitleWidget(title="Test", darkmode=True)` displays styled title
- ✅ Multiple titles in different corners work independently
- ✅ All font settings (size, color, weight) are respected

**LogoWidget:**
- ✅ Creating `LogoWidget(logo="url", logo_width=200)` displays resized logo
- ✅ Multiple logos in different corners work independently
- ✅ Base64 and URL logos both work

**SearchWidget:**
- ✅ Creating `SearchWidget(search_field="hover_text")` enables search
- ✅ Typing in search box filters points correctly
- ✅ Custom search_field is respected

**LegendWidget:**
- ✅ Creating `LegendWidget()` creates container for dynamic legend
- ✅ Legend updates when colormap changes
- ✅ Legend shows/hides based on colormap type

**ColormapSelectorWidget:**
- ✅ Creating `ColormapSelectorWidget(available_colormaps=["viridis", "plasma"])` shows selector
- ✅ Clicking colormap changes visualization
- ✅ Multiple colormaps in list all work

**TopicTreeWidget:**
- ✅ Creating `TopicTreeWidget()` builds interactive tree from label data
- ✅ Tree highlights based on viewport
- ✅ Custom button actions work (if configured)
- ✅ Tree expands/collapses correctly

**HistogramWidget:**
- ✅ Creating `HistogramWidget(histogram_data=dates)` renders working histogram
- ✅ Brushing histogram filters points
- ✅ Multiple histograms with different data work independently
- ✅ All styling parameters (colors, size) are respected

### General Success Criteria

- ✅ No difference in functionality between `use_widgets=True` and `use_widgets=False`
- ✅ Mixed widget types in single plot all work together
- ✅ Widget data flows cleanly: widget instance → template → JS → DOM
- ✅ All existing tests pass
- ✅ New tests cover all 7 widget types
- ✅ Documentation includes examples for each widget type
- ✅ Drawer widgets (any type) work correctly in drawers
- ✅ Corner widgets (any type) work correctly in corners
- ✅ Widget container IDs are unique and properly namespaced
