"""
Widget system for DataMapPlot interactive visualizations.

This module provides a base class and pre-defined widget implementations for
adding modular UI components to interactive data map plots. Widgets can be
placed in corner quadrants or slide-out drawers.
"""

from datamapplot.config import ConfigManager

cfg = ConfigManager()

# Valid widget locations
VALID_LOCATIONS = [
    "top-left",
    "top-right",
    "bottom-left",
    "bottom-right",
    "drawer-left",
    "drawer-right",
    "drawer-bottom",
]

# Map legacy selection-handler location names to widget-convention names
_LOCATION_ALIASES = {
    "left-drawer": "drawer-left",
    "right-drawer": "drawer-right",
    "bottom-drawer": "drawer-bottom",
}


def normalize_location(location):
    """Normalize a location string to the canonical widget convention.

    Accepts both widget-convention names (``"drawer-left"``) and legacy
    selection-handler names (``"left-drawer"``) and returns the canonical form.

    Parameters
    ----------
    location : str or None
        The location string to normalize.

    Returns
    -------
    str or None
        The normalized location, or *None* if the input was *None*.

    Raises
    ------
    ValueError
        If the location is not a recognized value.
    """
    if location is None:
        return None
    canonical = _LOCATION_ALIASES.get(location, location)
    if canonical not in VALID_LOCATIONS:
        raise ValueError(
            f"Invalid location '{location}'. "
            f"Must be one of: {', '.join(VALID_LOCATIONS)} "
            f"(or legacy aliases: {', '.join(_LOCATION_ALIASES.keys())})"
        )
    return canonical


class WidgetBase:
    """Base class for widgets. Widgets are modular UI components that can be added
    to the interactive plot in various locations (corners or drawers).

    Widgets encapsulate HTML structure, CSS styling, and JavaScript behavior, similar
    to SelectionHandlers but focused on UI components rather than interaction handling.

    Parameters
    ----------
    widget_id : str
        Unique identifier for this widget instance

    title : str or None, optional
        Display title for the widget. Default is None.

    location : str, optional
        Default location for the widget. One of: "top-left", "top-right",
        "bottom-left", "bottom-right", "drawer-left", "drawer-right".
        Default is "top-left".

    order : int, optional
        Stacking order within the location (lower numbers appear first).
        Default is 0.

    collapsible : bool, optional
        Whether the widget can be collapsed/expanded by the user.
        Default is False.

    visible : bool, optional
        Whether the widget is visible by default. Default is True.

    dependencies : list, optional
        A list of URLs for external dependencies required by the widget.
        Default is an empty list.

    **kwargs
        Additional keyword arguments for subclass customization.
    """

    def __init__(
        self,
        widget_id,
        title=None,
        location="top-left",
        order=0,
        collapsible=False,
        visible=True,
        dependencies=None,
        **kwargs,
    ):
        self.widget_id = widget_id
        self.title = title
        self.location = normalize_location(location)
        self.order = order
        self.collapsible = collapsible
        self.visible = visible
        # Use instance dependencies if provided, otherwise fall back to class-level dependencies
        if dependencies is not None:
            self.dependencies = dependencies
        elif not hasattr(self, "dependencies"):
            # Only set to empty list if no class-level dependencies exist
            self.dependencies = []
        # If class has dependencies attribute, it will be used via attribute lookup
        self.kwargs = kwargs

    @property
    def html(self):
        """Return the HTML content for the widget.

        Returns
        -------
        str
            HTML string to be rendered in the widget container
        """
        return ""

    @property
    def css(self):
        """Return the CSS styling for the widget.

        Returns
        -------
        str
            CSS string for widget-specific styles
        """
        return ""

    @property
    def javascript(self):
        """Return the JavaScript code for the widget.

        Returns
        -------
        str
            JavaScript string for widget behavior and interactions
        """
        return ""

    def get_container_id(self):
        """Get the HTML container ID for this widget.

        Returns
        -------
        str
            The container element ID
        """
        return f"{self.widget_id}-container"

    def get_config(self):
        """Get the configuration dictionary for this widget.

        Returns
        -------
        dict
            Configuration dictionary containing widget metadata
        """
        return {
            "widget_id": self.widget_id,
            "title": self.title,
            "location": self.location,
            "order": self.order,
            "collapsible": self.collapsible,
            "visible": self.visible,
        }

    def render(self, **context):
        """Render the widget with the given context.

        This method can be overridden to provide dynamic rendering based on
        context values passed from the rendering pipeline.

        Parameters
        ----------
        **context
            Context variables for rendering

        Returns
        -------
        dict
            Dictionary with keys 'html', 'css', 'javascript'
        """
        return {
            "html": self.html,
            "css": self.css,
            "javascript": self.javascript,
        }


class SelectionWidget(WidgetBase):
    """A lightweight widget for selection-handler display components.

    Provides a standard container with show/hide support and drawer integration.
    Selection handlers that display UI on selection can embed a ``SelectionWidget``
    to manage their container instead of hand-rolling DOM creation in JavaScript.

    The container starts hidden (``visible=False``) and exposes ``show()`` /
    ``hide()`` JavaScript helpers that selection handler callbacks can call.

    Parameters
    ----------
    widget_id : str
        Unique identifier for the widget container.

    title : str or None, optional
        Optional title displayed at the top of the container.

    location : str, optional
        Placement location. Default is ``"top-right"``.

    order : int, optional
        Stacking order within the location. Default is 50.

    width : int or str or None, optional
        CSS width for the container. If an int, treated as pixels.
        ``None`` means ``fit-content``. Default is ``None``.

    max_height : str, optional
        CSS max-height for the scrollable content area. Default is ``"80vh"``.

    container_css_class : str, optional
        CSS class(es) for the outer container element.
        Default is ``"container-box more-opaque stack-box"``.

    inner_html : str, optional
        Additional HTML to render inside the container (after the title).
        Default is ``""``.

    **kwargs
        Forwarded to :class:`WidgetBase`.
    """

    def __init__(
        self,
        widget_id,
        title=None,
        location="top-right",
        order=50,
        width=None,
        max_height="80vh",
        container_css_class="container-box more-opaque stack-box",
        inner_html="",
        **kwargs,
    ):
        super().__init__(
            widget_id=widget_id,
            title=title,
            location=location,
            order=order,
            visible=False,
            **kwargs,
        )
        self.width = width
        self.max_height = max_height
        self.container_css_class = container_css_class
        self.inner_html = inner_html

    @property
    def html(self):
        container_id = self.get_container_id()
        width_style = ""
        if self.width is not None:
            w = (
                f"{self.width}px"
                if isinstance(self.width, (int, float))
                else self.width
            )
            width_style = f"width: {w};"

        title_html = ""
        if self.title:
            title_html = f'<div class="selection-widget-title">' f"{self.title}</div>"

        return (
            f'<div id="{container_id}" '
            f'class="{self.container_css_class}" '
            f'data-order="{self.order}" '
            f'style="display:none;{width_style}">'
            f"{title_html}"
            f'<div id="{container_id}-content" '
            f'class="selection-widget-content">'
            f"{self.inner_html}"
            f"</div></div>"
        )

    @property
    def css(self):
        container_id = self.get_container_id()
        return f"""
#{container_id} .selection-widget-title {{
    font-weight: bold;
    font-size: 14px;
    margin-bottom: 8px;
}}
#{container_id} .selection-widget-content {{
    overflow-y: auto;
    max-height: {self.max_height};
}}
"""

    @property
    def javascript(self):
        container_id = self.get_container_id()
        location = self.location or "top-right"
        return f"""
// SelectionWidget helpers for {container_id}
(function() {{
    const _swContainer = document.getElementById("{container_id}");

    // Append to the correct stack/drawer if not already placed by the template
    if (_swContainer && !_swContainer.parentElement.classList.contains("stack")) {{
        const stack = findStackContainer("{location}");
        if (stack) {{
            stack.appendChild(_swContainer);
        }}
    }}

    // Expose show/hide helpers on the DOM element
    if (_swContainer) {{
        _swContainer.showWidget = function() {{
            _swContainer.style.display = "block";
            if ("{location}".startsWith("drawer-") && window.drawerManager) {{
                const dir = "{location}".replace("drawer-", "");
                window.drawerManager.openDrawer(dir);
            }}
        }};
        _swContainer.hideWidget = function() {{
            _swContainer.style.display = "none";
            if ("{location}".startsWith("drawer-") && window.drawerManager) {{
                const dir = "{location}".replace("drawer-", "");
                window.drawerManager.closeDrawer(dir);
            }}
        }};
    }}
}})();
"""


class TitleWidget(WidgetBase):
    """Widget for displaying plot title and subtitle.

    Parameters
    ----------
    title : str
        Main title text

    sub_title : str, optional
        Subtitle text. Default is "".

    title_font_family : str, optional
        Font family for title. Default is "Roboto".

    title_font_size : int, optional
        Font size for title in points. Default is 36.

    sub_title_font_size : int, optional
        Font size for subtitle in points. Default is 18.

    title_font_weight : int, optional
        Font weight for title. Default is 600.

    title_font_color : str or None, optional
        Color for title text. If None, will be set based on darkmode.
        Default is None.

    sub_title_font_color : str or None, optional
        Color for subtitle text. If None, will be set based on darkmode.
        Default is None.

    darkmode : bool, optional
        Whether darkmode is enabled. Affects default colors. Default is False.

    **kwargs
        Additional keyword arguments passed to WidgetBase
    """

    dependencies = []  # Pure HTML widget

    @cfg.complete(unconfigurable={"self"})
    def __init__(
        self,
        title,
        sub_title="",
        title_font_family="Roboto",
        title_font_size=36,
        sub_title_font_size=18,
        title_font_weight=600,
        title_font_color=None,
        sub_title_font_color=None,
        darkmode=False,
        **kwargs,
    ):
        kwargs.setdefault("widget_id", "title")
        kwargs.setdefault("location", "top-left")
        kwargs.setdefault("order", 0)
        super().__init__(**kwargs)

        self.title_text = title
        self.sub_title = sub_title
        self.title_font_family = title_font_family
        self.title_font_size = title_font_size
        self.sub_title_font_size = sub_title_font_size
        self.title_font_weight = title_font_weight
        self.darkmode = darkmode

        # Set colors based on darkmode if not explicitly provided
        if title_font_color is None:
            self.title_font_color = "#ffffff" if darkmode else "#000000"
        else:
            self.title_font_color = title_font_color

        if sub_title_font_color is None:
            self.sub_title_font_color = "#aaaaaa" if darkmode else "#666666"
        else:
            self.sub_title_font_color = sub_title_font_color

    @property
    def html(self):
        html = f"""
<div id="{self.get_container_id()}" class="container-box">
  <span
    id="main-title"
    style="font-family:{self.title_font_family};font-size:{self.title_font_size}pt;font-weight:{self.title_font_weight};color:{self.title_font_color}"
  >
    {self.title_text}
  </span>
"""
        if self.sub_title:
            html += f"""
  <br />
  <span
    style="font-family:{self.title_font_family};font-size:{self.sub_title_font_size}pt;color:{self.sub_title_font_color}"
  >
    {self.sub_title}
  </span>
"""
        html += "</div>"
        return html


class SearchWidget(WidgetBase):
    """Widget for text search functionality.

    Parameters
    ----------
    placeholder : str, optional
        Placeholder text for search input. Default is "🔍".

    search_field : str, optional
        Field name to search in the data. Default is "hover_text".

    **kwargs
        Additional keyword arguments passed to WidgetBase
    """

    dependencies = []  # Uses core datamap.js

    @cfg.complete(unconfigurable={"self"})
    def __init__(self, placeholder="🔍", search_field="hover_text", **kwargs):
        kwargs.setdefault("widget_id", "search")
        kwargs.setdefault("location", "top-left")
        kwargs.setdefault("order", 1)
        super().__init__(**kwargs)

        self.placeholder = placeholder
        self.search_field = search_field

    @property
    def html(self):
        return f"""
<div id="{self.get_container_id()}" class="container-box">
  <input autocomplete="off" type="search" id="text-search" placeholder="{self.placeholder}" />
</div>
"""

    @property
    def css(self):
        return f"""
#{self.get_container_id()} {{
  width: fit-content;
}}
"""

    @property
    def javascript(self):
        """Configure search functionality in DataMap."""
        import json

        return f"""
(function() {{
    const searchInput = document.querySelector('#text-search');
    if (!searchInput) return;
    
    function initSearch() {{
        if (window.datamap) {{
            window.datamap.searchField = {json.dumps(self.search_field)};
            console.log('Search widget configured for field:', window.datamap.searchField);
        }}
    }}
    
    if (window.datamap) {{
        initSearch();
    }} else {{
        document.addEventListener('datamapDataLoaded', initSearch);
    }}
}})();
"""


class TopicTreeWidget(WidgetBase):
    """Widget for displaying hierarchical topic tree.

    Parameters
    ----------
    title : str, optional
        Title for the topic tree. Default is "Topic Tree".

    font_size : str, optional
        Font size for tree text. Default is "12pt".

    max_width : str, optional
        Maximum width of the tree. Default is "30vw".

    max_height : str, optional
        Maximum height of the tree. Default is "42vh".

    color_bullets : bool, optional
        Whether to color bullets by cluster color. Default is False.

    button_on_click : str or None, optional
        JavaScript code for button click handling. Default is None.

    button_icon : str, optional
        Icon/text for tree buttons. Default is "&#128194;".

    **kwargs
        Additional keyword arguments passed to WidgetBase
    """

    dependencies = ["js:topic_tree", "css:topic_tree"]

    @cfg.complete(unconfigurable={"self"})
    def __init__(
        self,
        title="Topic Tree",
        font_size="12pt",
        max_width="30vw",
        max_height="42vh",
        color_bullets=False,
        button_on_click=None,
        button_icon="&#128194;",
        **kwargs,
    ):
        kwargs.setdefault("widget_id", "topic-tree")
        kwargs.setdefault("location", "top-left")
        kwargs.setdefault("order", 2)
        super().__init__(**kwargs)

        self.tree_title = title
        self.font_size = font_size
        self.max_width = max_width
        self.max_height = max_height
        self.color_bullets = color_bullets
        self.button_on_click = button_on_click
        self.button_icon = button_icon

    @property
    def html(self):
        return f'<div id="{self.get_container_id()}" class="container-box"></div>'

    @property
    def javascript(self):
        """Generate JS to instantiate TopicTree component."""
        import json

        container_id = self.get_container_id()
        widget_id = self.widget_id

        # Handle button click code
        button_handlers = ""
        if self.button_on_click:
            # Extract the code between quotes if it's a string literal
            click_code = self.button_on_click
            if click_code.startswith(('"', "'")) and click_code.endswith(('"', "'")):
                click_code = click_code[1:-1]
            button_handlers = f"""
    topicTree.container.querySelectorAll('.topic-tree-btn').forEach(button => {{
        button.addEventListener('click', function() {{
            var label = window.datamap.labelData.find(l => l.id === this.dataset.labelId);
            {click_code}
        }});
    }});
"""

        return f"""
(function() {{
    const container = document.querySelector('#{container_id}');
    if (!container) return;
    
    function setup() {{
        if (!window.datamap || !window.datamap.labelData) {{
            console.warn('DataMap or label data not available for topic tree');
            return;
        }}
        
        const topicTree = new TopicTree(
            container,
            window.datamap,
            {str(self.button_on_click is not None).lower()},
            {json.dumps(self.button_icon) if self.button_on_click else 'null'},
            {{
                title: {json.dumps(self.tree_title)},
                maxWidth: {json.dumps(self.max_width)},
                maxHeight: {json.dumps(self.max_height)},
                fontSize: {json.dumps(self.font_size)},
                colorBullets: {str(self.color_bullets).lower()},
            }}
        );
        {button_handlers}
        // Set up viewport highlighting
        const debounced = debounce(({{viewState, interactionState}}) => {{
            const userIsInteracting = interactionState && Object.values(interactionState).every(Boolean);
            if (!userIsInteracting) {{
                const visible = getVisibleTextData(viewState, window.datamap.labelData);
                if (visible) {{
                    topicTree.highlightElements(visible);
                }}
            }}
        }}, 150);
        
        window.datamap.onViewStateChange('topicTree', debounced);
        
        // Store reference
        window.datamap.widgets = window.datamap.widgets || {{}};
        window.datamap.widgets['{widget_id}'] = topicTree;
    }}
    
    if (window.datamap && window.datamap.labelData) {{
        setup();
    }} else {{
        document.addEventListener('datamapDataLoaded', setup);
    }}
}})();
"""


class HistogramWidget(WidgetBase):
    """Widget for displaying interactive histogram.

    Parameters
    ----------
    histogram_data : array-like
        Data for histogram bins

    histogram_width : int, optional
        Width of histogram in pixels. Default is 300.

    histogram_height : int, optional
        Height of histogram in pixels. Default is 70.

    histogram_title : str, optional
        Title for the histogram. Default is "".

    histogram_bin_count : int, optional
        Number of bins. Default is 20.

    histogram_bin_fill_color : str, optional
        Fill color for bins. Default is "#6290C3".

    histogram_bin_selected_fill_color : str, optional
        Fill color for selected bins. Default is "#2EBFA5".

    histogram_bin_unselected_fill_color : str, optional
        Fill color for unselected bins. Default is "#9E9E9E".

    histogram_bin_context_fill_color : str, optional
        Fill color for context bins. Default is "#E6E6E6".

    histogram_log_scale : bool, optional
        Use log scale for y-axis. Default is False.

    **kwargs
        Additional keyword arguments passed to WidgetBase
    """

    dependencies = ["js:d3", "js:histogram", "css:histogram"]

    @cfg.complete(unconfigurable={"self"})
    def __init__(
        self,
        histogram_data=None,
        histogram_width=300,
        histogram_height=70,
        histogram_title="",
        histogram_bin_count=20,
        histogram_bin_fill_color="#6290C3",
        histogram_bin_selected_fill_color="#2EBFA5",
        histogram_bin_unselected_fill_color="#9E9E9E",
        histogram_bin_context_fill_color="#E6E6E6",
        histogram_log_scale=False,
        **kwargs,
    ):
        kwargs.setdefault("widget_id", "d3histogram")
        kwargs.setdefault("location", "bottom-left")
        kwargs.setdefault("order", 1)
        super().__init__(**kwargs)

        self.histogram_data = histogram_data
        self.histogram_width = histogram_width
        self.histogram_height = histogram_height
        self.histogram_title = histogram_title
        self.histogram_bin_count = histogram_bin_count
        self.histogram_bin_fill_color = histogram_bin_fill_color
        self.histogram_bin_selected_fill_color = histogram_bin_selected_fill_color
        self.histogram_bin_unselected_fill_color = histogram_bin_unselected_fill_color
        self.histogram_bin_context_fill_color = histogram_bin_context_fill_color
        self.histogram_log_scale = histogram_log_scale

    @property
    def html(self):
        return f'<div id="{self.get_container_id()}" class="container-box stack-box"></div>'

    @property
    def javascript(self):
        """Generate JS to instantiate D3Histogram with data."""
        import json

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
        
        if (!window.datamap) {{
            console.warn('DataMap not available for histogram');
            return;
        }}
        
        // Selection callback for histogram interaction
        const chartSelectionCallback = chartSelectedIndices => {{
            if (chartSelectedIndices === null) {{
                window.datamap.removeSelection('{container_id}');
            }} else {{
                window.datamap.addSelection(chartSelectedIndices, '{container_id}');
            }}
        }};
        
        // Use D3Histogram factory method with proper parameters
        const histogram = D3Histogram.create({{
            data: histData,
            chartContainerId: '{container_id}',
            chartWidth: {self.histogram_width},
            chartHeight: {self.histogram_height},
            title: {json.dumps(self.histogram_title)},
            binCount: {self.histogram_bin_count},
            binDefaultFillColor: {json.dumps(self.histogram_bin_fill_color)},
            binSelectedFillColor: {json.dumps(self.histogram_bin_selected_fill_color)},
            binUnselectedFillColor: {json.dumps(self.histogram_bin_unselected_fill_color)},
            binContextFillColor: {json.dumps(self.histogram_bin_context_fill_color)},
            logScale: {str(self.histogram_log_scale).lower()},
            chartSelectionCallback: chartSelectionCallback,
        }});
        
        if (histogram) {{
            window.datamap.connectHistogram(histogram);
            
            // Store reference
            window.datamap.widgets = window.datamap.widgets || {{}};
            window.datamap.widgets['{widget_id}'] = histogram;
        }}
    }}
        
    if (window.datamap) {{
        setup();
    }} else {{
        document.addEventListener('datamapDataLoaded', setup);
    }}
}})();
"""


class ColormapSelectorWidget(WidgetBase):
    """Widget for colormap selection and legend display.

    Parameters
    ----------
    colormap_metadata : list of dict, optional
        Metadata for available colormaps. Default is None.

    **kwargs
        Additional keyword arguments passed to WidgetBase
    """

    dependencies = ["js:colormap_selector", "css:colormap_selector"]

    @cfg.complete(unconfigurable={"self"})
    def __init__(
        self,
        colormaps=None,
        colormap_metadata=None,
        colormap_rawdata=None,
        cluster_layer_colormaps=None,
        **kwargs,
    ):
        kwargs.setdefault("widget_id", "colormap-selector")
        kwargs.setdefault("location", "bottom-left")
        kwargs.setdefault("order", 0)
        super().__init__(**kwargs)

        self.colormaps = colormaps
        self.colormap_metadata = colormap_metadata
        self.colormap_rawdata = colormap_rawdata
        self.cluster_layer_colormaps = cluster_layer_colormaps

    @property
    def html(self):
        return f'<div id="{self.get_container_id()}" class="container-box stack-box"></div>'

    @property
    def javascript(self):
        """Generate JS to instantiate ColormapSelector."""
        container_id = self.get_container_id()
        widget_id = self.widget_id

        return f"""
(function() {{
    const container = document.querySelector('#{container_id}');
    if (!container) return;
    
    function setup() {{
        const colorMaps = window.widgetColormapData?.['{widget_id}'];
        if (!colorMaps || colorMaps.length === 0) {{
            console.warn('No colormaps provided for widget {widget_id}');
            return;
        }}
        
        if (!window.datamap) {{
            console.warn('DataMap not available for colormap selector');
            return;
        }}
        
        // Get legendContainer from datamap (set by LegendWidget)
        const legendContainer = window.datamap.legendContainer;
        if (!legendContainer) {{
            console.warn('Legend container not available for colormap selector');
        }}
        
        // Get color data from datamap (loaded by data loading pipeline)
        const colorData = window.datamap.colorData;
        if (!colorData) {{
            console.warn('Color data not available yet for colormap selector');
            return;
        }}
        
        // Use correct class name and parameter order
        const selector = new ColormapSelectorTool(
            colorMaps,
            container,
            colorData,
            legendContainer,
            window.datamap
        );
        
        // Store reference
        window.datamap.colorSelector = selector;
        window.datamap.widgets = window.datamap.widgets || {{}};
        window.datamap.widgets['{widget_id}'] = selector;
    }}
    
    if (window.datamap && window.datamap.colorData) {{
        setup();
    }} else {{
        document.addEventListener('datamapDataLoaded', setup);
    }}
}})();
"""


class LegendWidget(WidgetBase):
    """Widget for displaying color legend.

    Parameters
    ----------
    **kwargs
        Additional keyword arguments passed to WidgetBase
    """

    dependencies = ["js:colormap_selector"]

    @cfg.complete(unconfigurable={"self"})
    def __init__(self, **kwargs):
        kwargs.setdefault("widget_id", "legend")
        kwargs.setdefault("location", "top-right")
        kwargs.setdefault("order", 0)
        super().__init__(**kwargs)

    @property
    def html(self):
        return f'<div id="{self.get_container_id()}" class="container-box stack-box" style="display:none;"></div>'

    @property
    def javascript(self):
        """Register legend container with DataMap."""
        container_id = self.get_container_id()
        widget_id = self.widget_id

        return f"""
(function() {{
    const container = document.querySelector('#{container_id}');
    if (!container) return;
    
    function setup() {{
        if (!window.datamap) return;
        
        // Register container with datamap for dynamic updates
        window.datamap.legendContainer = container;
        
        // Initial setup if colormap already set
        if (window.datamap.currentColormap && window.datamap.updateLegend) {{
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
        document.addEventListener('datamapDataLoaded', setup);
    }}
}})();
"""


class LogoWidget(WidgetBase):
    """Widget for displaying a logo image.

    Parameters
    ----------
    logo : str
        Path or base64 encoded image data for the logo

    logo_width : int, optional
        Width of the logo in pixels. Default is 256.

    **kwargs
        Additional keyword arguments passed to WidgetBase
    """

    dependencies = []  # Pure HTML widget

    @cfg.complete(unconfigurable={"self"})
    def __init__(self, logo, logo_width=256, **kwargs):
        kwargs.setdefault("widget_id", "logo")
        kwargs.setdefault("location", "bottom-right")
        kwargs.setdefault("order", 0)
        super().__init__(**kwargs)

        self.logo = logo
        self.logo_width = logo_width

    @property
    def html(self):
        return f"""
<div id="{self.get_container_id()}" class="container-box stack-box">
  <img src="{self.logo}" style="width:{self.logo_width}px" />
</div>
"""

    @property
    def css(self):
        return """
img {
  display: block;
  margin-left: auto;
  margin-right: auto;
}
"""


class SelectionControlWidget(WidgetBase):
    """Widget for controlling selection modes and managing selection groups.

    Provides UI controls for:
    - Selection modes: Replace, Add (union), Remove (subtract), Intersect
    - Named selection groups: Save, load, and delete selection sets
    - Clear all selections

    This widget integrates with the DataSelectionManager to provide advanced
    selection control workflows.

    Parameters
    ----------
    show_modes : bool, optional
        Whether to show selection mode buttons. Default is True.

    show_groups : bool, optional
        Whether to show selection groups UI. Default is True.

    show_clear : bool, optional
        Whether to show clear selection button. Default is True.

    max_groups : int, optional
        Maximum number of selection groups allowed. Default is 10.

    **kwargs
        Additional keyword arguments passed to WidgetBase
    """

    dependencies = ["js:selection_control", "css:selection_control"]

    @cfg.complete(unconfigurable={"self"})
    def __init__(
        self,
        show_modes=True,
        show_groups=True,
        show_clear=True,
        max_groups=10,
        **kwargs,
    ):
        kwargs.setdefault("widget_id", "selection-control")
        kwargs.setdefault("location", "top-right")
        kwargs.setdefault("order", 0)
        super().__init__(**kwargs)

        self.show_modes = show_modes
        self.show_groups = show_groups
        self.show_clear = show_clear
        self.max_groups = max_groups

    @property
    def html(self):
        return f'<div id="{self.get_container_id()}" class="container-box"></div>'

    @property
    def javascript(self):
        """Generate JS to instantiate SelectionControl."""
        import json

        container_id = self.get_container_id()
        widget_id = self.widget_id

        return f"""
(function() {{
    const container = document.querySelector('#{container_id}');
    if (!container) return;
    
    function setup() {{
        if (!window.datamap) {{
            console.warn('DataMap not available for selection control');
            return;
        }}
        
        const selectionControl = new SelectionControl(
            container,
            window.datamap,
            {{
                showModes: {str(self.show_modes).lower()},
                showGroups: {str(self.show_groups).lower()},
                showClear: {str(self.show_clear).lower()},
                maxGroups: {self.max_groups}
            }}
        );
        
        // Store reference
        window.datamap.widgets = window.datamap.widgets || {{}};
        window.datamap.widgets['{widget_id}'] = selectionControl;
    }}
    
    if (window.datamap) {{
        setup();
    }} else {{
        document.addEventListener('datamapDataLoaded', setup);
    }}
}})();
"""


class LayerToggleWidget(WidgetBase):
    """Widget for controlling visibility and opacity of map layers.

    Provides checkboxes to show/hide layers and sliders to adjust opacity.
    Can control points, labels, cluster boundaries, and other visualization layers.

    Parameters
    ----------
    layers : list of dict, optional
        List of layer configurations. Each dict should have:
        - 'id': str - Layer identifier ('points', 'labels', 'clusters')
        - 'label': str - Display name for the layer
        - 'visible': bool - Initial visibility
        - 'opacity': float - Initial opacity (0.0-1.0)
        Default layers: points, labels, clusters

    show_opacity : bool, optional
        Whether to show opacity sliders. Default is True.

    **kwargs
        Additional keyword arguments passed to WidgetBase
    """

    dependencies = ["js:layer_toggle", "css:layer_toggle"]

    @cfg.complete(unconfigurable={"self"})
    def __init__(
        self,
        layers=None,
        show_opacity=True,
        **kwargs,
    ):
        kwargs.setdefault("widget_id", "layer-toggle")
        kwargs.setdefault("location", "top-right")
        kwargs.setdefault("order", 1)
        super().__init__(**kwargs)

        self.layers = layers or [
            {
                "id": "imageLayer",
                "label": "Background",
                "visible": True,
                "opacity": 1.0,
            },
            {
                "id": "edgeLayer",
                "label": "Edges",
                "visible": True,
                "opacity": 1.0,
            },
            {
                "id": "dataPointLayer",
                "label": "Points",
                "visible": True,
                "opacity": 1.0,
            },
            {
                "id": "hexagonLayer",
                "label": "Density Heatmap",
                "visible": True,
                "opacity": 0.6,
            },
            {"id": "labelLayer", "label": "Labels", "visible": True, "opacity": 1.0},
            {
                "id": "boundaryLayer",
                "label": "Cluster Boundaries",
                "visible": True,
                "opacity": 0.5,
            },
        ]
        self.show_opacity = show_opacity

    @property
    def html(self):
        return f'<div id="{self.get_container_id()}" class="container-box"></div>'

    @property
    def javascript(self):
        """Generate JS to instantiate LayerToggle."""
        import json

        container_id = self.get_container_id()
        widget_id = self.widget_id

        return f"""
(function() {{
    const container = document.querySelector('#{container_id}');
    if (!container) return;
    
    function setup() {{
        if (!window.datamap) {{
            console.warn('DataMap not available for layer toggle');
            return;
        }}
        
        const layerToggle = new LayerToggle(
            container,
            window.datamap,
            {{
                layers: {json.dumps(self.layers)},
                showOpacity: {str(self.show_opacity).lower()}
            }}
        );
        
        // Store reference
        window.datamap.widgets = window.datamap.widgets || {{}};
        window.datamap.widgets['{widget_id}'] = layerToggle;
    }}
    
    if (window.datamap && window.datamap.deckgl && window.datamap.layers && window.datamap.layers.length > 0) {{
        setup();
    }} else {{
        document.addEventListener('datamapDataLoaded', setup);
    }}
}})();
"""


class MiniMapWidget(WidgetBase):
    """Widget displaying a minimap overview of the entire dataset.

    Shows all data points with a viewport indicator showing the current view.
    Click on the minimap to navigate to different regions.

    Parameters
    ----------
    width : int, optional
        Width of the minimap in pixels. Default is 200.

    height : int, optional
        Height of the minimap in pixels. Default is 150.

    update_throttle : int, optional
        Throttle time for viewport updates in milliseconds. Default is 200.

    border_color : str, optional
        Color of the viewport indicator border. Default is "#3ba5e7".

    border_width : int, optional
        Width of the viewport indicator border in pixels. Default is 2.

    background_color : str, optional
        Background color of the minimap. Default is "#f5f5f5".

    point_color : str, optional
        Color of the data points. Default is "#666666".

    point_size : int, optional
        Size of data points in pixels. Default is 2.

    **kwargs
        Additional keyword arguments passed to WidgetBase
    """

    dependencies = ["js:minimap", "css:minimap"]

    @cfg.complete(unconfigurable={"self"})
    def __init__(
        self,
        width=200,
        height=150,
        update_throttle=200,
        border_color="#3ba5e7",
        border_width=2,
        background_color="#f5f5f5",
        point_color="#666666",
        point_size=2,
        **kwargs,
    ):
        kwargs.setdefault("widget_id", "minimap")
        kwargs.setdefault("location", "bottom-right")
        kwargs.setdefault("order", 0)
        super().__init__(**kwargs)

        self.width = width
        self.height = height
        self.update_throttle = update_throttle
        self.border_color = border_color
        self.border_width = border_width
        self.background_color = background_color
        self.point_color = point_color
        self.point_size = point_size

    @property
    def html(self):
        return f'<div id="{self.get_container_id()}" class="container-box"></div>'

    @property
    def javascript(self):
        """Generate JS to instantiate MiniMap."""
        import json

        container_id = self.get_container_id()
        widget_id = self.widget_id

        return f"""
(function() {{
    const container = document.querySelector('#{container_id}');
    if (!container) return;
    
    function setup() {{
        if (!window.datamap) {{
            console.warn('DataMap not available for minimap');
            return;
        }}
        
        const minimap = new MiniMap(
            container,
            window.datamap,
            {{
                width: {self.width},
                height: {self.height},
                updateThrottle: {self.update_throttle},
                borderColor: {json.dumps(self.border_color)},
                borderWidth: {self.border_width},
                backgroundColor: {json.dumps(self.background_color)},
                pointColor: {json.dumps(self.point_color)},
                pointSize: {self.point_size},
                mirrorY: {str("bottom" in self.location and "drawer" not in self.location).lower()}
            }}
        );
        
        // Store reference
        window.datamap.widgets = window.datamap.widgets || {{}};
        window.datamap.widgets['{widget_id}'] = minimap;
    }}
    
    if (window.datamap && window.datamap.pointData) {{
        setup();
    }} else {{
        document.addEventListener('datamapDataLoaded', setup);
    }}
}})();
"""


class RESTSearchWidget(WidgetBase):
    """Server-side search widget that queries a REST endpoint.

    Parameters
    ----------
    endpoint_url : str
        Full URL to the search endpoint (e.g., "https://api.example.com/search")

    http_method : str, optional (default: "POST")
        HTTP method to use: "POST" or "GET"

    request_body_template : dict, optional
        Template for request body. Use "{query}" placeholder for search term.
        Example: {"q": "{query}", "limit": 50}
        If None, defaults to {"query": "{query}"}

    auth_headers : dict, optional
        HTTP headers for authentication.
        Example: {"Authorization": "Bearer YOUR_TOKEN"}

    response_path : str, optional (default: "results")
        JSON path to array of results. Use dot notation for nested paths.
        Example: "data.items" for response like {"data": {"items": [...]}}

    id_field : str, optional (default: "id")
        Field name in response objects that contains point IDs to select

    debounce_ms : int, optional (default: 300)
        Milliseconds to wait after typing before sending request

    min_query_length : int, optional (default: 2)
        Minimum characters required before search is triggered

    placeholder : str, optional
        Placeholder text for search input

    show_result_count : bool, optional (default: True)
        Whether to display "X results found" message

    timeout_ms : int, optional (default: 10000)
        Request timeout in milliseconds

    **kwargs
        Additional keyword arguments passed to WidgetBase
    """

    dependencies = ["js:rest_search", "css:rest_search"]

    @cfg.complete(unconfigurable={"self"})
    def __init__(
        self,
        endpoint_url,
        http_method="POST",
        request_body_template=None,
        auth_headers=None,
        response_path="results",
        id_field="id",
        debounce_ms=300,
        min_query_length=2,
        placeholder="Search...",
        show_result_count=True,
        timeout_ms=10000,
        **kwargs,
    ):
        kwargs.setdefault("widget_id", "rest-search")
        kwargs.setdefault("location", "drawer-left")
        kwargs.setdefault("order", 1)
        super().__init__(**kwargs)

        self.endpoint_url = endpoint_url
        self.http_method = http_method.upper()
        self.request_body_template = request_body_template or {"query": "{query}"}
        self.auth_headers = auth_headers or {}
        self.response_path = response_path
        self.id_field = id_field
        self.debounce_ms = debounce_ms
        self.min_query_length = min_query_length
        self.placeholder = placeholder
        self.show_result_count = show_result_count
        self.timeout_ms = timeout_ms

        # Validate HTTP method
        if self.http_method not in ["GET", "POST"]:
            raise ValueError("http_method must be 'GET' or 'POST'")

    @property
    def html(self):
        """Return HTML container for the widget."""
        return (
            f'<div id="{self.get_container_id()}" class="rest-search-container"></div>'
        )

    @property
    def javascript(self):
        """Generate JS to instantiate RESTSearchWidget."""
        import json

        container_id = self.get_container_id()
        widget_id = self.widget_id
        config = self.collect_widget_data()

        return f"""
(function() {{
    const containerId = '{container_id}';
    const config = {json.dumps(config)};
    
    function setup() {{
        if (!window.datamap) {{
            console.warn('DataMap not available for REST search widget');
            return;
        }}
        
        const widget = new RESTSearchWidget(containerId, config, window.datamap);
        
        // Store reference
        window.datamap.widgets = window.datamap.widgets || {{}};
        window.datamap.widgets['{widget_id}'] = widget;
    }}
    
    if (window.datamap) {{
        setup();
    }} else {{
        document.addEventListener('datamapDataLoaded', setup);
    }}
}})();
"""

    def collect_widget_data(self):
        """Collect widget configuration for template."""
        return {
            "endpoint_url": self.endpoint_url,
            "http_method": self.http_method,
            "request_body_template": self.request_body_template,
            "auth_headers": self.auth_headers,
            "response_path": self.response_path,
            "id_field": self.id_field,
            "debounce_ms": self.debounce_ms,
            "min_query_length": self.min_query_length,
            "placeholder": self.placeholder,
            "show_result_count": self.show_result_count,
            "timeout_ms": self.timeout_ms,
        }


class AnnotationWidget(WidgetBase):
    """Annotation widget for adding persistent markup to the map.

    Supports adding text labels, arrows, and shapes (circles, rectangles)
    that persist across sessions via JSON export/import.

    Parameters
    ----------
    initial_annotations : list, optional
        List of annotation dicts to load on initialization.
        Each annotation should have: {"type": "text"|"arrow"|"circle", ...}

    allow_text : bool, optional (default: True)
        Enable text annotation tool

    allow_arrows : bool, optional (default: True)
        Enable arrow annotation tool

    allow_circles : bool, optional (default: True)
        Enable circle annotation tool

    allow_rectangles : bool, optional (default: True)
        Enable rectangle annotation tool

    default_text_color : str, optional (default: "#000000")
        Default color for text annotations

    default_text_size : int, optional (default: 14)
        Default font size for text annotations

    default_stroke_color : str, optional (default: "#FF0000")
        Default color for arrows and shapes

    default_stroke_width : int, optional (default: 2)
        Default line width for arrows and shapes

    default_fill_opacity : float, optional (default: 0.2)
        Default fill opacity for circles and rectangles (0-1)

    enable_export : bool, optional (default: True)
        Show export button to download annotations as JSON

    enable_import : bool, optional (default: True)
        Show import button to load annotations from JSON file

    snap_to_points : bool, optional (default: False)
        If True, annotation coordinates snap to nearest data point

    snap_distance : float, optional (default: 20)
        Pixel distance for snap-to-point behavior

    **kwargs
        Additional keyword arguments passed to WidgetBase
    """

    dependencies = ["js:annotation", "css:annotation"]

    @cfg.complete(unconfigurable={"self"})
    def __init__(
        self,
        initial_annotations=None,
        allow_text=True,
        allow_arrows=True,
        allow_circles=True,
        allow_rectangles=True,
        default_text_color="#000000",
        default_text_size=14,
        default_stroke_color="#FF0000",
        default_stroke_width=2,
        default_fill_opacity=0.2,
        enable_export=True,
        enable_import=True,
        snap_to_points=False,
        snap_distance=20,
        **kwargs,
    ):
        kwargs.setdefault("widget_id", "annotation")
        kwargs.setdefault("location", "drawer-left")
        kwargs.setdefault("order", 2)
        super().__init__(**kwargs)

        self.initial_annotations = initial_annotations or []
        self.allow_text = allow_text
        self.allow_arrows = allow_arrows
        self.allow_circles = allow_circles
        self.allow_rectangles = allow_rectangles
        self.default_text_color = default_text_color
        self.default_text_size = default_text_size
        self.default_stroke_color = default_stroke_color
        self.default_stroke_width = default_stroke_width
        self.default_fill_opacity = default_fill_opacity
        self.enable_export = enable_export
        self.enable_import = enable_import
        self.snap_to_points = snap_to_points
        self.snap_distance = snap_distance

    @property
    def html(self):
        """Return HTML container for the widget."""
        return (
            f'<div id="{self.get_container_id()}" class="annotation-container"></div>'
        )

    @property
    def javascript(self):
        """Generate JS to instantiate AnnotationWidget."""
        import json

        container_id = self.get_container_id()
        widget_id = self.widget_id
        config = self.collect_widget_data()

        return f"""
(function() {{
    const containerId = '{container_id}';
    const config = {json.dumps(config)};
    
    function setup() {{
        if (!window.datamap) {{
            console.warn('DataMap not available for annotation widget');
            return;
        }}
        
        const widget = new AnnotationWidget(containerId, config, window.datamap);
        
        // Store reference
        window.datamap.widgets = window.datamap.widgets || {{}};
        window.datamap.widgets['{widget_id}'] = widget;
    }}
    
    if (window.datamap) {{
        setup();
    }} else {{
        document.addEventListener('datamapDataLoaded', setup);
    }}
}})();
"""

    def collect_widget_data(self):
        """Collect widget configuration for template."""
        return {
            "initial_annotations": self.initial_annotations,
            "tools": {
                "text": self.allow_text,
                "arrow": self.allow_arrows,
                "circle": self.allow_circles,
                "rectangle": self.allow_rectangles,
            },
            "defaults": {
                "text_color": self.default_text_color,
                "text_size": self.default_text_size,
                "stroke_color": self.default_stroke_color,
                "stroke_width": self.default_stroke_width,
                "fill_opacity": self.default_fill_opacity,
            },
            "features": {
                "export": self.enable_export,
                "import": self.enable_import,
                "snap_to_points": self.snap_to_points,
                "snap_distance": self.snap_distance,
            },
        }
