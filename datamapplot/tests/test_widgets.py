"""Tests for the widget system."""

import pytest
import json
import tempfile
from pathlib import Path

import numpy as np

from datamapplot.widgets import (
    WidgetBase,
    TitleWidget,
    SearchWidget,
    TopicTreeWidget,
    HistogramWidget,
    ColormapSelectorWidget,
    LegendWidget,
    LogoWidget,
    SelectionControlWidget,
    LayerToggleWidget,
    MiniMapWidget,
    RESTSearchWidget,
    AnnotationWidget,
)
from datamapplot.widget_helpers import (
    WidgetConfig,
    VALID_LOCATIONS,
    load_widget_config_from_json,
    validate_widget_layout,
    merge_widget_configs,
    create_widget_from_config,
    widgets_from_legacy_params,
    group_widgets_by_location,
    get_drawer_enabled,
    collect_widget_dependencies,
    collect_widget_data,
    legacy_widget_flags_from_widgets,
    update_drawer_enabled_for_handlers,
)


class TestWidgetBase:
    """Tests for the WidgetBase class."""

    def test_widget_base_creation(self):
        """Test basic widget creation."""
        widget = WidgetBase(widget_id="test-widget")
        assert widget.widget_id == "test-widget"
        assert widget.location == "top-left"
        assert widget.order == 0
        assert widget.visible is True
        assert widget.collapsible is False

    def test_widget_base_custom_location(self):
        """Test widget with custom location."""
        widget = WidgetBase(
            widget_id="test", location="drawer-left", order=5, collapsible=True
        )
        assert widget.location == "drawer-left"
        assert widget.order == 5
        assert widget.collapsible is True

    def test_widget_container_id(self):
        """Test get_container_id method."""
        widget = WidgetBase(widget_id="my-widget")
        assert widget.get_container_id() == "my-widget-container"

    def test_widget_get_config(self):
        """Test get_config method."""
        widget = WidgetBase(
            widget_id="test", title="Test Widget", location="bottom-right"
        )
        config = widget.get_config()
        assert config["widget_id"] == "test"
        assert config["title"] == "Test Widget"
        assert config["location"] == "bottom-right"

    def test_widget_render(self):
        """Test render method returns dict with html, css, javascript."""
        widget = WidgetBase(widget_id="test")
        result = widget.render()
        assert "html" in result
        assert "css" in result
        assert "javascript" in result


class TestTitleWidget:
    """Tests for the TitleWidget class."""

    def test_title_widget_creation(self):
        """Test basic title widget creation."""
        widget = TitleWidget(title="My Title")
        assert widget.title_text == "My Title"
        assert widget.widget_id == "title"
        assert widget.location == "top-left"

    def test_title_widget_with_subtitle(self):
        """Test title widget with subtitle."""
        widget = TitleWidget(title="Main", sub_title="Sub")
        assert widget.title_text == "Main"
        assert widget.sub_title == "Sub"

    def test_title_widget_html_contains_title(self):
        """Test that HTML contains the title text."""
        widget = TitleWidget(title="Test Title")
        assert "Test Title" in widget.html


class TestSearchWidget:
    """Tests for the SearchWidget class."""

    def test_search_widget_creation(self):
        """Test basic search widget creation."""
        widget = SearchWidget()
        assert widget.widget_id == "search"
        assert widget.placeholder == "🔍"

    def test_search_widget_custom_placeholder(self):
        """Test search widget with custom placeholder."""
        widget = SearchWidget(placeholder="Search...")
        assert widget.placeholder == "Search..."

    def test_search_widget_html_contains_input(self):
        """Test that HTML contains search input."""
        widget = SearchWidget()
        assert 'type="search"' in widget.html


class TestWidgetConfig:
    """Tests for the WidgetConfig dataclass."""

    def test_widget_config_defaults(self):
        """Test default WidgetConfig values."""
        config = WidgetConfig(widget_id="test")
        assert config.location == "top-left"
        assert config.order == 0
        assert config.visible is True
        assert config.collapsible is False

    def test_widget_config_custom_values(self):
        """Test WidgetConfig with custom values."""
        config = WidgetConfig(
            widget_id="test", location="drawer-right", order=5, collapsible=True
        )
        assert config.location == "drawer-right"
        assert config.order == 5
        assert config.collapsible is True

    def test_widget_config_invalid_location(self):
        """Test that invalid location raises ValueError."""
        with pytest.raises(ValueError):
            WidgetConfig(widget_id="test", location="invalid-location")

    def test_widget_config_to_dict(self):
        """Test to_dict method."""
        config = WidgetConfig(widget_id="test", location="bottom-left")
        d = config.to_dict()
        assert d["widget_id"] == "test"
        assert d["location"] == "bottom-left"


class TestLoadWidgetConfig:
    """Tests for loading widget configuration from JSON."""

    def test_load_widget_config_from_json(self):
        """Test loading config from JSON file."""
        config_data = {
            "title": {"location": "top-left", "order": 0},
            "search": {"location": "top-left", "order": 1},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config_data, f)
            f.flush()

            configs = load_widget_config_from_json(f.name)
            assert "title" in configs
            assert "search" in configs
            assert configs["title"].location == "top-left"
            assert configs["search"].order == 1

    def test_load_widget_config_file_not_found(self):
        """Test that missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_widget_config_from_json("/nonexistent/path.json")


class TestValidateWidgetLayout:
    """Tests for validating widget layouts."""

    def test_validate_widget_layout_dict(self):
        """Test validating a dict layout."""
        layout = {
            "title": {"location": "top-left"},
            "search": {"location": "drawer-left"},
        }
        validated = validate_widget_layout(layout)
        assert isinstance(validated["title"], WidgetConfig)
        assert validated["search"].location == "drawer-left"

    def test_validate_widget_layout_with_config_objects(self):
        """Test validating layout with WidgetConfig objects."""
        layout = {"title": WidgetConfig(widget_id="title", location="top-left")}
        validated = validate_widget_layout(layout)
        assert validated["title"].location == "top-left"

    def test_validate_widget_layout_invalid_type(self):
        """Test that invalid layout type raises ValueError."""
        with pytest.raises(ValueError):
            validate_widget_layout("not a dict")


class TestMergeWidgetConfigs:
    """Tests for merging widget configurations."""

    def test_merge_configs_user_overrides_default(self):
        """Test that user config overrides default."""
        default = {
            "title": WidgetConfig(widget_id="title", location="top-left"),
            "search": WidgetConfig(widget_id="search", location="top-left"),
        }
        user = {"title": WidgetConfig(widget_id="title", location="drawer-left")}
        merged = merge_widget_configs(default, user)
        assert merged["title"].location == "drawer-left"
        assert merged["search"].location == "top-left"

    def test_merge_configs_with_none(self):
        """Test merging with None values."""
        default = {"title": WidgetConfig(widget_id="title")}
        merged = merge_widget_configs(default, None)
        assert "title" in merged


class TestCreateWidgetFromConfig:
    """Tests for the widget factory function."""

    def test_create_title_widget(self):
        """Test creating a title widget."""
        widget = create_widget_from_config("title", title="Test")
        assert isinstance(widget, TitleWidget)
        assert widget.title_text == "Test"

    def test_create_search_widget(self):
        """Test creating a search widget."""
        widget = create_widget_from_config("search")
        assert isinstance(widget, SearchWidget)

    def test_create_widget_with_config(self):
        """Test creating widget with config object."""
        config = WidgetConfig(widget_id="title", location="drawer-right", order=5)
        widget = create_widget_from_config("title", config=config, title="Test")
        assert widget.location == "drawer-right"
        assert widget.order == 5

    def test_create_unknown_widget_raises(self):
        """Test that unknown widget type raises ValueError."""
        with pytest.raises(ValueError):
            create_widget_from_config("unknown_type")


class TestWidgetsFromLegacyParams:
    """Tests for converting legacy parameters to widgets."""

    def test_legacy_title(self):
        """Test converting legacy title parameter."""
        widgets = widgets_from_legacy_params(title="Test Title")
        assert len(widgets) == 1
        assert isinstance(widgets[0], TitleWidget)

    def test_legacy_search(self):
        """Test converting legacy enable_search parameter."""
        widgets = widgets_from_legacy_params(enable_search=True)
        assert len(widgets) == 1
        assert isinstance(widgets[0], SearchWidget)

    def test_legacy_multiple(self):
        """Test converting multiple legacy parameters."""
        widgets = widgets_from_legacy_params(
            title="Test", enable_search=True, logo="data:image/png;base64,test"
        )
        assert len(widgets) == 3


class TestGroupWidgetsByLocation:
    """Tests for grouping widgets by location."""

    def test_group_widgets(self):
        """Test basic grouping."""
        widgets = [
            TitleWidget(title="Test"),
            SearchWidget(location="drawer-left"),
        ]
        grouped = group_widgets_by_location(widgets)
        assert len(grouped["top-left"]) == 1
        assert len(grouped["drawer-left"]) == 1

    def test_group_widgets_with_layout_override(self):
        """Test grouping with layout override."""
        widgets = [TitleWidget(title="Test")]
        layout = {"title": WidgetConfig(widget_id="title", location="drawer-right")}
        grouped = group_widgets_by_location(widgets, layout)
        assert len(grouped["drawer-right"]) == 1
        assert len(grouped["top-left"]) == 0

    def test_group_widgets_sorted_by_order(self):
        """Test that widgets are sorted by order."""
        widgets = [
            SearchWidget(order=2),
            TitleWidget(title="Test", order=1),
        ]
        grouped = group_widgets_by_location(widgets)
        # Both are in top-left by default
        assert grouped["top-left"][0].order == 1
        assert grouped["top-left"][1].order == 2


class TestGetDrawerEnabled:
    """Tests for determining if drawers are enabled."""

    def test_drawer_disabled_when_empty(self):
        """Test that drawers are disabled when no widgets in them."""
        grouped = {loc: [] for loc in VALID_LOCATIONS}
        enabled = get_drawer_enabled(grouped)
        assert enabled["left"] is False
        assert enabled["right"] is False

    def test_left_drawer_enabled(self):
        """Test that left drawer is enabled when it has widgets."""
        grouped = {loc: [] for loc in VALID_LOCATIONS}
        grouped["drawer-left"] = [SearchWidget()]
        enabled = get_drawer_enabled(grouped)
        assert enabled["left"] is True
        assert enabled["right"] is False

    def test_right_drawer_enabled(self):
        """Test that right drawer is enabled when it has widgets."""
        grouped = {loc: [] for loc in VALID_LOCATIONS}
        grouped["drawer-right"] = [SearchWidget()]
        enabled = get_drawer_enabled(grouped)
        assert enabled["left"] is False
        assert enabled["right"] is True


class TestCollectWidgetDependencies:
    """Tests for collecting widget dependencies."""

    def test_collect_empty(self):
        """Test collecting from widgets with no dependencies."""
        widgets = [TitleWidget(title="Test")]
        deps = collect_widget_dependencies(widgets)
        assert deps["js_files"] == set()
        assert deps["css_files"] == set()
        assert deps["external_js"] == set()

    def test_collect_with_js_prefix_dependencies(self):
        """Test collecting from widget with js: prefixed dependencies."""
        widget = WidgetBase(
            widget_id="test",
            dependencies=["js:histogram", "css:histogram"],
        )
        deps = collect_widget_dependencies([widget])
        assert "histogram" in deps["js_files"]
        assert "histogram" in deps["css_files"]

    def test_collect_external_url_dependencies(self):
        """Test collecting external URL dependencies."""
        widget = WidgetBase(
            widget_id="test",
            dependencies=[
                "https://example.com/lib.js",
            ],
        )
        deps = collect_widget_dependencies([widget])
        assert "https://example.com/lib.js" in deps["external_js"]

    def test_collect_no_duplicates(self):
        """Test that duplicate dependencies are removed."""
        widget1 = WidgetBase(widget_id="w1", dependencies=["js:histogram"])
        widget2 = WidgetBase(widget_id="w2", dependencies=["js:histogram"])
        deps = collect_widget_dependencies([widget1, widget2])
        assert len(deps["js_files"]) == 1

    def test_collect_mixed_dependency_formats(self):
        """Test collecting dependencies in different formats."""
        widget = WidgetBase(
            widget_id="test",
            dependencies=[
                "js:histogram",
                "css:topic_tree",
                "https://cdn.example.com/d3.js",
            ],
        )
        deps = collect_widget_dependencies([widget])
        assert "histogram" in deps["js_files"]
        assert "topic_tree" in deps["css_files"]
        assert "https://cdn.example.com/d3.js" in deps["external_js"]


class TestTitleWidgetDarkmode:
    """Tests for TitleWidget darkmode support."""

    def test_title_widget_lightmode_default_colors(self):
        """Test that lightmode uses dark text colors."""
        widget = TitleWidget(title="Test", darkmode=False)
        assert widget.title_font_color == "#000000"
        assert widget.sub_title_font_color == "#666666"

    def test_title_widget_darkmode_default_colors(self):
        """Test that darkmode uses light text colors."""
        widget = TitleWidget(title="Test", darkmode=True)
        assert widget.title_font_color == "#ffffff"
        assert widget.sub_title_font_color == "#aaaaaa"

    def test_title_widget_explicit_colors_override_darkmode(self):
        """Test that explicit colors override darkmode defaults."""
        widget = TitleWidget(
            title="Test",
            darkmode=True,
            title_font_color="#ff0000",
            sub_title_font_color="#00ff00",
        )
        assert widget.title_font_color == "#ff0000"
        assert widget.sub_title_font_color == "#00ff00"

    def test_title_widget_html_uses_correct_colors(self):
        """Test that HTML output contains the correct color values."""
        widget = TitleWidget(title="Test", sub_title="Sub", darkmode=True)
        html = widget.html
        assert "color:#ffffff" in html
        assert "color:#aaaaaa" in html


class TestLogoWidget:
    """Tests for the LogoWidget class."""

    def test_logo_widget_creation(self):
        """Test basic logo widget creation."""
        widget = LogoWidget(logo="https://example.com/logo.png")
        assert widget.widget_id == "logo"
        assert widget.logo == "https://example.com/logo.png"

    def test_logo_widget_default_location(self):
        """Test logo widget default location is bottom-right."""
        widget = LogoWidget(logo="https://example.com/logo.png")
        assert widget.location == "bottom-right"

    def test_logo_widget_custom_dimensions(self):
        """Test logo widget with custom dimensions."""
        widget = LogoWidget(
            logo="https://example.com/logo.png",
            logo_width=200,
        )
        assert widget.logo_width == 200

    def test_logo_widget_html_contains_image(self):
        """Test that HTML contains the logo image."""
        widget = LogoWidget(logo="https://example.com/logo.png")
        assert "https://example.com/logo.png" in widget.html
        assert "<img" in widget.html


class TestWidgetLocationValidation:
    """Tests for widget location validation."""

    def test_all_valid_locations(self):
        """Test that all expected locations are valid."""
        expected_locations = [
            "top-left",
            "top-right",
            "bottom-left",
            "bottom-right",
            "drawer-left",
            "drawer-right",
        ]
        for loc in expected_locations:
            config = WidgetConfig(widget_id="test", location=loc)
            assert config.location == loc

    def test_drawer_locations_detected(self):
        """Test that drawer locations are properly detected."""
        grouped = {loc: [] for loc in VALID_LOCATIONS}
        grouped["drawer-left"] = [SearchWidget(location="drawer-left")]
        grouped["drawer-right"] = [TitleWidget(title="Test", location="drawer-right")]

        enabled = get_drawer_enabled(grouped)
        assert enabled["left"] is True
        assert enabled["right"] is True

    def test_corner_locations_dont_enable_drawers(self):
        """Test that corner locations don't enable drawers."""
        grouped = {loc: [] for loc in VALID_LOCATIONS}
        grouped["top-left"] = [TitleWidget(title="Test")]
        grouped["bottom-right"] = [LogoWidget(logo="test.png")]

        enabled = get_drawer_enabled(grouped)
        assert enabled["left"] is False
        assert enabled["right"] is False


@pytest.mark.interactive
class TestWidgetHtmlRendering:
    """Integration tests for widget HTML rendering in interactive plots."""

    @pytest.fixture
    def simple_point_data(self):
        """Create simple point data for testing."""
        import numpy as np
        import pandas as pd

        n_points = 50
        np.random.seed(42)
        return pd.DataFrame(
            {
                "x": np.random.randn(n_points),
                "y": np.random.randn(n_points),
                "r": np.random.randint(0, 255, n_points, dtype=np.uint8),
                "g": np.random.randint(0, 255, n_points, dtype=np.uint8),
                "b": np.random.randint(0, 255, n_points, dtype=np.uint8),
                "a": np.full(n_points, 255, dtype=np.uint8),
                "hover_text": [f"Point {i}" for i in range(n_points)],
            }
        )

    @pytest.fixture
    def simple_label_data(self):
        """Create simple label data for testing."""
        import numpy as np
        import pandas as pd

        n_labels = 3
        np.random.seed(42)
        return pd.DataFrame(
            {
                "x": np.random.randn(n_labels),
                "y": np.random.randn(n_labels),
                "r": np.random.randint(0, 255, n_labels, dtype=np.uint8),
                "g": np.random.randint(0, 255, n_labels, dtype=np.uint8),
                "b": np.random.randint(0, 255, n_labels, dtype=np.uint8),
                "a": np.full(n_labels, 255, dtype=np.uint8),
                "label": [f"Cluster {i}" for i in range(n_labels)],
                "size": np.random.uniform(10, 100, n_labels),
            }
        )

    def test_darkmode_body_class(self, simple_point_data, simple_label_data):
        """Test that darkmode adds class to body element."""
        from datamapplot.interactive_rendering import render_html

        html_content = render_html(
            simple_point_data,
            simple_label_data,
            inline_data=True,
            darkmode=True,
        )

        assert '<body class="darkmode">' in html_content

    def test_lightmode_no_body_class(self, simple_point_data, simple_label_data):
        """Test that lightmode doesn't add darkmode class to body."""
        from datamapplot.interactive_rendering import render_html

        html_content = render_html(
            simple_point_data,
            simple_label_data,
            inline_data=True,
            darkmode=False,
        )

        # Should have body tag but not with darkmode class
        assert "<body>" in html_content or "<body " in html_content
        assert '<body class="darkmode">' not in html_content

    def test_widget_in_corner_location(self, simple_point_data, simple_label_data):
        """Test that widgets render in corner locations."""
        from datamapplot.interactive_rendering import render_html

        widgets = [
            TitleWidget(title="Test Title", location="top-left"),
        ]

        html_content = render_html(
            simple_point_data,
            simple_label_data,
            inline_data=True,
            widgets=widgets,
        )

        assert "Test Title" in html_content
        assert "top-left" in html_content

    def test_widget_in_drawer_location(self, simple_point_data, simple_label_data):
        """Test that widgets in drawer locations enable drawer CSS."""
        from datamapplot.interactive_rendering import render_html

        widgets = [
            SearchWidget(location="drawer-left"),
        ]

        html_content = render_html(
            simple_point_data,
            simple_label_data,
            inline_data=True,
            widgets=widgets,
        )

        # Should have drawer container and handle
        assert "drawer-container" in html_content
        assert "drawer-handle" in html_content
        assert "drawer-left" in html_content

    def test_drawer_handle_arrows(self, simple_point_data, simple_label_data):
        """Test that drawer handles have correct arrow icons."""
        from datamapplot.interactive_rendering import render_html

        widgets = [
            SearchWidget(location="drawer-left"),
            TitleWidget(title="Test", location="drawer-right"),
        ]

        html_content = render_html(
            simple_point_data,
            simple_label_data,
            inline_data=True,
            widgets=widgets,
        )

        # Left drawer handle should have right-pointing arrow (▶)
        # Right drawer handle should have left-pointing arrow (◀)
        assert "▶" in html_content  # Left drawer arrow
        assert "◀" in html_content  # Right drawer arrow

    def test_title_widget_darkmode_colors_in_html(
        self, simple_point_data, simple_label_data
    ):
        """Test that TitleWidget uses correct colors in darkmode."""
        from datamapplot.interactive_rendering import render_html

        widgets = [
            TitleWidget(title="Dark Title", darkmode=True, location="top-left"),
        ]

        html_content = render_html(
            simple_point_data,
            simple_label_data,
            inline_data=True,
            darkmode=True,
            widgets=widgets,
        )

        # Title should have white color in darkmode
        assert "color:#ffffff" in html_content
        assert "Dark Title" in html_content

    def test_title_widget_lightmode_colors_in_html(
        self, simple_point_data, simple_label_data
    ):
        """Test that TitleWidget uses correct colors in lightmode."""
        from datamapplot.interactive_rendering import render_html

        widgets = [
            TitleWidget(title="Light Title", darkmode=False, location="top-left"),
        ]

        html_content = render_html(
            simple_point_data,
            simple_label_data,
            inline_data=True,
            darkmode=False,
            widgets=widgets,
        )

        # Title should have black color in lightmode
        assert "color:#000000" in html_content
        assert "Light Title" in html_content

    def test_drawer_darkmode_css_present(self, simple_point_data, simple_label_data):
        """Test that drawer darkmode CSS rules are included."""
        from datamapplot.interactive_rendering import render_html

        widgets = [
            SearchWidget(location="drawer-left"),
        ]

        html_content = render_html(
            simple_point_data,
            simple_label_data,
            inline_data=True,
            darkmode=True,
            widgets=widgets,
        )

        # Should include darkmode CSS rules for drawer
        assert "body.darkmode .drawer-container" in html_content

    def test_multiple_widgets_different_locations(
        self, simple_point_data, simple_label_data
    ):
        """Test multiple widgets in different locations."""
        from datamapplot.interactive_rendering import render_html

        widgets = [
            TitleWidget(title="Top Title", location="top-left", order=0),
            SearchWidget(location="drawer-left", order=0),
            LogoWidget(
                logo="https://example.com/logo.png", location="bottom-right", order=0
            ),
        ]

        html_content = render_html(
            simple_point_data,
            simple_label_data,
            inline_data=True,
            widgets=widgets,
        )

        assert "Top Title" in html_content
        assert "text-search" in html_content or "search" in html_content.lower()
        assert "https://example.com/logo.png" in html_content
        assert "top-left" in html_content
        assert "drawer-left" in html_content
        assert "bottom-right" in html_content


# ============================================================
# Additional widget class tests
# ============================================================


class TestLegendWidget:
    """Tests for the LegendWidget class."""

    def test_creation_defaults(self):
        """Test basic legend widget creation with defaults."""
        widget = LegendWidget()
        assert widget.widget_id == "legend"
        assert widget.location == "top-right"
        assert widget.order == 0

    def test_dependencies(self):
        """Test that legend widget declares colormap_selector JS dependency."""
        widget = LegendWidget()
        assert "js:colormap_selector" in widget.dependencies

    def test_html_output(self):
        """Test that HTML contains the legend container."""
        widget = LegendWidget()
        html = widget.html
        assert widget.get_container_id() in html
        assert "container-box" in html

    def test_javascript_output(self):
        """Test that JS output references the widget id and registers container."""
        widget = LegendWidget()
        js = widget.javascript
        assert widget.get_container_id() in js
        assert "legendContainer" in js

    def test_custom_params(self):
        """Test legend widget with custom widget_id and location."""
        widget = LegendWidget(widget_id="custom-legend", location="bottom-left")
        assert widget.widget_id == "custom-legend"
        assert widget.location == "bottom-left"


class TestTopicTreeWidgetExtended:
    """Extended tests for the TopicTreeWidget class."""

    def test_creation_defaults(self):
        """Test basic topic tree widget creation with defaults."""
        widget = TopicTreeWidget()
        assert widget.widget_id == "topic-tree"
        assert widget.location == "top-left"
        assert widget.order == 2

    def test_dependencies(self):
        """Test that topic tree widget declares correct dependencies."""
        widget = TopicTreeWidget()
        assert "js:topic_tree" in widget.dependencies
        assert "css:topic_tree" in widget.dependencies

    def test_tree_title_attribute(self):
        """Test that tree_title stores the title (distinct from WidgetBase.title)."""
        widget = TopicTreeWidget(title="My Tree")
        assert widget.tree_title == "My Tree"

    def test_default_params(self):
        """Test default parameter values."""
        widget = TopicTreeWidget()
        assert widget.tree_title == "Topic Tree"
        assert widget.font_size == "12pt"
        assert widget.max_width == "30vw"
        assert widget.max_height == "42vh"
        assert widget.color_bullets is False
        assert widget.button_on_click is None

    def test_html_output_contains_container(self):
        """Test that HTML contains the topic-tree container."""
        widget = TopicTreeWidget()
        html = widget.html
        assert widget.get_container_id() in html
        assert "container-box" in html

    def test_javascript_output(self):
        """Test that JS output references TopicTree and widget id."""
        widget = TopicTreeWidget(title="My Topics")
        js = widget.javascript
        assert "TopicTree" in js
        assert widget.get_container_id() in js
        assert "My Topics" in js

    def test_custom_params(self):
        """Test topic tree with custom parameters."""
        widget = TopicTreeWidget(
            title="Custom",
            font_size="14pt",
            max_width="50vw",
            max_height="80vh",
            color_bullets=True,
        )
        assert widget.tree_title == "Custom"
        assert widget.font_size == "14pt"
        assert widget.max_width == "50vw"
        assert widget.max_height == "80vh"
        assert widget.color_bullets is True

    def test_button_on_click(self):
        """Test topic tree with button click handler."""
        widget = TopicTreeWidget(
            button_on_click="console.log(label)",
            button_icon="🔗",
        )
        js = widget.javascript
        assert "console.log(label)" in js
        assert widget.button_icon == "🔗"


class TestHistogramWidgetExtended:
    """Extended tests for the HistogramWidget class."""

    def test_creation_defaults(self):
        """Test basic histogram widget creation with defaults."""
        widget = HistogramWidget()
        assert widget.widget_id == "d3histogram"
        assert widget.location == "bottom-left"
        assert widget.order == 1

    def test_default_params(self):
        """Test default parameter values."""
        widget = HistogramWidget()
        assert widget.histogram_width == 300
        assert widget.histogram_height == 70
        assert widget.histogram_title == ""
        assert widget.histogram_bin_count == 20
        assert widget.histogram_log_scale is False
        assert widget.histogram_data is None

    def test_dependencies(self):
        """Test that histogram widget declares correct dependencies."""
        widget = HistogramWidget()
        assert "js:d3" in widget.dependencies
        assert "js:histogram" in widget.dependencies
        assert "css:histogram" in widget.dependencies

    def test_custom_dimensions(self):
        """Test histogram with custom dimensions and bin count."""
        widget = HistogramWidget(
            histogram_width=500,
            histogram_height=120,
            histogram_bin_count=50,
        )
        assert widget.histogram_width == 500
        assert widget.histogram_height == 120
        assert widget.histogram_bin_count == 50

    def test_custom_colors(self):
        """Test histogram with custom color settings."""
        widget = HistogramWidget(
            histogram_bin_fill_color="#FF0000",
            histogram_bin_selected_fill_color="#00FF00",
            histogram_bin_unselected_fill_color="#0000FF",
            histogram_bin_context_fill_color="#AAAAAA",
        )
        assert widget.histogram_bin_fill_color == "#FF0000"
        assert widget.histogram_bin_selected_fill_color == "#00FF00"
        assert widget.histogram_bin_unselected_fill_color == "#0000FF"
        assert widget.histogram_bin_context_fill_color == "#AAAAAA"

    def test_histogram_data_stored(self):
        """Test that histogram_data is stored on the widget."""
        data = [1.0, 2.0, 3.0, 4.0, 5.0]
        widget = HistogramWidget(histogram_data=data)
        assert widget.histogram_data == data

    def test_histogram_data_numpy(self):
        """Test that numpy array histogram_data is stored."""
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        widget = HistogramWidget(histogram_data=data)
        np.testing.assert_array_equal(widget.histogram_data, data)

    def test_html_output(self):
        """Test that HTML contains histogram container."""
        widget = HistogramWidget()
        html = widget.html
        assert widget.get_container_id() in html
        assert "container-box" in html

    def test_javascript_output(self):
        """Test that JS output references D3Histogram and configuration."""
        widget = HistogramWidget(
            histogram_width=400,
            histogram_bin_count=30,
            histogram_log_scale=True,
        )
        js = widget.javascript
        assert "D3Histogram" in js
        assert widget.get_container_id() in js
        assert "400" in js
        assert "30" in js
        assert "true" in js  # log scale

    def test_log_scale(self):
        """Test histogram with log scale enabled."""
        widget = HistogramWidget(histogram_log_scale=True)
        assert widget.histogram_log_scale is True


class TestColormapSelectorWidgetExtended:
    """Extended tests for the ColormapSelectorWidget class."""

    def test_creation_defaults(self):
        """Test basic colormap selector creation with defaults."""
        widget = ColormapSelectorWidget()
        assert widget.widget_id == "colormap-selector"
        assert widget.location == "bottom-left"
        assert widget.order == 0

    def test_dependencies(self):
        """Test that colormap selector declares correct dependencies."""
        widget = ColormapSelectorWidget()
        assert "js:colormap_selector" in widget.dependencies
        assert "css:colormap_selector" in widget.dependencies

    def test_colormap_metadata(self):
        """Test colormap selector with metadata."""
        metadata = [
            {"name": "viridis", "type": "sequential"},
            {"name": "plasma", "type": "sequential"},
        ]
        widget = ColormapSelectorWidget(colormap_metadata=metadata)
        assert widget.colormap_metadata == metadata
        assert len(widget.colormap_metadata) == 2

    def test_colormap_rawdata(self):
        """Test colormap selector stores rawdata."""
        rawdata = {"cmap1": [[0, 0, 0], [255, 255, 255]]}
        widget = ColormapSelectorWidget(colormap_rawdata=rawdata)
        assert widget.colormap_rawdata == rawdata

    def test_cluster_layer_colormaps(self):
        """Test colormap selector stores cluster layer colormaps."""
        cluster_cmaps = {"layer0": "viridis", "layer1": "plasma"}
        widget = ColormapSelectorWidget(cluster_layer_colormaps=cluster_cmaps)
        assert widget.cluster_layer_colormaps == cluster_cmaps

    def test_html_output(self):
        """Test that HTML contains selector container."""
        widget = ColormapSelectorWidget()
        html = widget.html
        assert widget.get_container_id() in html
        assert "container-box" in html

    def test_javascript_output(self):
        """Test that JS output references ColormapSelectorTool."""
        widget = ColormapSelectorWidget()
        js = widget.javascript
        assert "ColormapSelectorTool" in js
        assert widget.get_container_id() in js

    def test_none_defaults(self):
        """Test that metadata fields default to None."""
        widget = ColormapSelectorWidget()
        assert widget.colormaps is None
        assert widget.colormap_metadata is None
        assert widget.colormap_rawdata is None
        assert widget.cluster_layer_colormaps is None


class TestSelectionControlWidget:
    """Tests for the SelectionControlWidget class."""

    def test_creation_defaults(self):
        """Test basic selection control widget creation."""
        widget = SelectionControlWidget()
        assert widget.widget_id == "selection-control"
        assert widget.location == "top-right"
        assert widget.order == 0
        assert widget.show_modes is True
        assert widget.show_groups is True
        assert widget.show_clear is True
        assert widget.max_groups == 10

    def test_custom_params(self):
        """Test selection control with custom parameters."""
        widget = SelectionControlWidget(
            show_modes=False,
            show_groups=False,
            show_clear=False,
            max_groups=5,
        )
        assert widget.show_modes is False
        assert widget.show_groups is False
        assert widget.show_clear is False
        assert widget.max_groups == 5

    def test_dependencies(self):
        """Test that selection control declares correct dependencies."""
        widget = SelectionControlWidget()
        assert "js:selection_control" in widget.dependencies
        assert "css:selection_control" in widget.dependencies

    def test_html_output(self):
        """Test that HTML contains selection control container."""
        widget = SelectionControlWidget()
        html = widget.html
        assert widget.get_container_id() in html
        assert "container-box" in html

    def test_javascript_output(self):
        """Test that JS output references SelectionControl and configuration."""
        widget = SelectionControlWidget(show_modes=False, max_groups=5)
        js = widget.javascript
        assert "SelectionControl" in js
        assert widget.get_container_id() in js
        assert "showModes: false" in js
        assert "maxGroups: 5" in js


class TestLayerToggleWidget:
    """Tests for the LayerToggleWidget class."""

    def test_creation_defaults(self):
        """Test basic layer toggle widget creation."""
        widget = LayerToggleWidget()
        assert widget.widget_id == "layer-toggle"
        assert widget.location == "top-right"
        assert widget.order == 1
        assert widget.show_opacity is True

    def test_default_layers(self):
        """Test that default layers are created."""
        widget = LayerToggleWidget()
        assert len(widget.layers) == 5
        layer_ids = [l["id"] for l in widget.layers]
        assert "imageLayer" in layer_ids
        assert "edgeLayer" in layer_ids
        assert "dataPointLayer" in layer_ids
        assert "labelLayer" in layer_ids
        assert "boundaryLayer" in layer_ids

    def test_custom_layers(self):
        """Test layer toggle with custom layers."""
        custom_layers = [
            {"id": "points", "label": "Points", "visible": True, "opacity": 1.0},
            {"id": "labels", "label": "Labels", "visible": False, "opacity": 0.5},
        ]
        widget = LayerToggleWidget(layers=custom_layers)
        assert len(widget.layers) == 2
        assert widget.layers[0]["id"] == "points"
        assert widget.layers[1]["visible"] is False

    def test_dependencies(self):
        """Test that layer toggle declares correct dependencies."""
        widget = LayerToggleWidget()
        assert "js:layer_toggle" in widget.dependencies
        assert "css:layer_toggle" in widget.dependencies

    def test_html_output(self):
        """Test that HTML contains layer toggle container."""
        widget = LayerToggleWidget()
        html = widget.html
        assert widget.get_container_id() in html
        assert "container-box" in html

    def test_javascript_output(self):
        """Test that JS output references LayerToggle."""
        widget = LayerToggleWidget()
        js = widget.javascript
        assert "LayerToggle" in js
        assert widget.get_container_id() in js

    def test_show_opacity_false(self):
        """Test layer toggle with opacity sliders disabled."""
        widget = LayerToggleWidget(show_opacity=False)
        assert widget.show_opacity is False
        js = widget.javascript
        assert "showOpacity: false" in js


class TestMiniMapWidget:
    """Tests for the MiniMapWidget class."""

    def test_creation_defaults(self):
        """Test basic minimap widget creation."""
        widget = MiniMapWidget()
        assert widget.widget_id == "minimap"
        assert widget.location == "bottom-right"
        assert widget.order == 0
        assert widget.width == 200
        assert widget.height == 150
        assert widget.update_throttle == 200

    def test_custom_dimensions(self):
        """Test minimap with custom dimensions."""
        widget = MiniMapWidget(width=300, height=250, update_throttle=100)
        assert widget.width == 300
        assert widget.height == 250
        assert widget.update_throttle == 100

    def test_custom_styling(self):
        """Test minimap with custom styling parameters."""
        widget = MiniMapWidget(
            border_color="#FF0000",
            border_width=3,
            background_color="#000000",
            point_color="#FFFFFF",
            point_size=4,
        )
        assert widget.border_color == "#FF0000"
        assert widget.border_width == 3
        assert widget.background_color == "#000000"
        assert widget.point_color == "#FFFFFF"
        assert widget.point_size == 4

    def test_dependencies(self):
        """Test that minimap declares correct dependencies."""
        widget = MiniMapWidget()
        assert "js:minimap" in widget.dependencies
        assert "css:minimap" in widget.dependencies

    def test_html_output(self):
        """Test that HTML contains minimap container."""
        widget = MiniMapWidget()
        html = widget.html
        assert widget.get_container_id() in html
        assert "container-box" in html

    def test_javascript_output(self):
        """Test that JS output references MiniMap and configuration."""
        widget = MiniMapWidget(width=300, height=200)
        js = widget.javascript
        assert "MiniMap" in js
        assert widget.get_container_id() in js
        assert "300" in js
        assert "200" in js

    def test_default_styling(self):
        """Test default styling values."""
        widget = MiniMapWidget()
        assert widget.border_color == "#3ba5e7"
        assert widget.border_width == 2
        assert widget.background_color == "#f5f5f5"
        assert widget.point_color == "#666666"
        assert widget.point_size == 2


class TestRESTSearchWidget:
    """Tests for the RESTSearchWidget class."""

    def test_creation_defaults(self):
        """Test basic REST search widget creation."""
        widget = RESTSearchWidget(endpoint_url="https://api.example.com/search")
        assert widget.widget_id == "rest-search"
        assert widget.location == "drawer-left"
        assert widget.order == 1
        assert widget.http_method == "POST"
        assert widget.endpoint_url == "https://api.example.com/search"

    def test_default_params(self):
        """Test default parameter values."""
        widget = RESTSearchWidget(endpoint_url="https://api.example.com/search")
        assert widget.request_body_template == {"query": "{query}"}
        assert widget.auth_headers == {}
        assert widget.response_path == "results"
        assert widget.id_field == "id"
        assert widget.debounce_ms == 300
        assert widget.min_query_length == 2
        assert widget.placeholder == "Search..."
        assert widget.show_result_count is True
        assert widget.timeout_ms == 10000

    def test_valid_http_methods(self):
        """Test that both GET and POST are accepted."""
        widget_post = RESTSearchWidget(
            endpoint_url="https://api.example.com/search",
            http_method="POST",
        )
        assert widget_post.http_method == "POST"

        widget_get = RESTSearchWidget(
            endpoint_url="https://api.example.com/search",
            http_method="GET",
        )
        assert widget_get.http_method == "GET"

    def test_http_method_case_normalization(self):
        """Test that http_method is uppercased."""
        widget = RESTSearchWidget(
            endpoint_url="https://api.example.com/search",
            http_method="get",
        )
        assert widget.http_method == "GET"

        widget2 = RESTSearchWidget(
            endpoint_url="https://api.example.com/search",
            http_method="post",
        )
        assert widget2.http_method == "POST"

    def test_invalid_http_method_raises(self):
        """Test that invalid HTTP methods raise ValueError."""
        with pytest.raises(ValueError, match="http_method must be 'GET' or 'POST'"):
            RESTSearchWidget(
                endpoint_url="https://api.example.com/search",
                http_method="PUT",
            )
        with pytest.raises(ValueError):
            RESTSearchWidget(
                endpoint_url="https://api.example.com/search",
                http_method="DELETE",
            )

    def test_collect_widget_data(self):
        """Test that collect_widget_data returns correct config dict."""
        widget = RESTSearchWidget(
            endpoint_url="https://api.example.com/search",
            http_method="POST",
            request_body_template={"q": "{query}", "limit": 50},
            auth_headers={"Authorization": "Bearer token123"},
            response_path="data.items",
            id_field="point_id",
            debounce_ms=500,
            min_query_length=3,
            placeholder="Find items...",
            show_result_count=False,
            timeout_ms=5000,
        )
        data = widget.collect_widget_data()
        assert data["endpoint_url"] == "https://api.example.com/search"
        assert data["http_method"] == "POST"
        assert data["request_body_template"] == {"q": "{query}", "limit": 50}
        assert data["auth_headers"] == {"Authorization": "Bearer token123"}
        assert data["response_path"] == "data.items"
        assert data["id_field"] == "point_id"
        assert data["debounce_ms"] == 500
        assert data["min_query_length"] == 3
        assert data["placeholder"] == "Find items..."
        assert data["show_result_count"] is False
        assert data["timeout_ms"] == 5000

    def test_dependencies(self):
        """Test that REST search declares correct dependencies."""
        widget = RESTSearchWidget(endpoint_url="https://api.example.com/search")
        assert "js:rest_search" in widget.dependencies
        assert "css:rest_search" in widget.dependencies

    def test_html_output(self):
        """Test that HTML contains REST search container."""
        widget = RESTSearchWidget(endpoint_url="https://api.example.com/search")
        html = widget.html
        assert widget.get_container_id() in html
        assert "rest-search-container" in html

    def test_javascript_output(self):
        """Test that JS output references RESTSearchWidget."""
        widget = RESTSearchWidget(endpoint_url="https://api.example.com/search")
        js = widget.javascript
        assert "RESTSearchWidget" in js
        assert widget.get_container_id() in js


class TestAnnotationWidget:
    """Tests for the AnnotationWidget class."""

    def test_creation_defaults(self):
        """Test basic annotation widget creation."""
        widget = AnnotationWidget()
        assert widget.widget_id == "annotation"
        assert widget.location == "drawer-left"
        assert widget.order == 2

    def test_default_params(self):
        """Test default parameter values."""
        widget = AnnotationWidget()
        assert widget.initial_annotations == []
        assert widget.allow_text is True
        assert widget.allow_arrows is True
        assert widget.allow_circles is True
        assert widget.allow_rectangles is True
        assert widget.default_text_color == "#000000"
        assert widget.default_text_size == 14
        assert widget.default_stroke_color == "#FF0000"
        assert widget.default_stroke_width == 2
        assert widget.default_fill_opacity == 0.2
        assert widget.enable_export is True
        assert widget.enable_import is True
        assert widget.snap_to_points is False
        assert widget.snap_distance == 20

    def test_custom_tool_config(self):
        """Test annotation widget with specific tools disabled."""
        widget = AnnotationWidget(
            allow_arrows=False,
            allow_rectangles=False,
        )
        assert widget.allow_arrows is False
        assert widget.allow_rectangles is False
        assert widget.allow_text is True
        assert widget.allow_circles is True

    def test_collect_widget_data_structure(self):
        """Test that collect_widget_data returns correct structure."""
        widget = AnnotationWidget()
        data = widget.collect_widget_data()
        assert "initial_annotations" in data
        assert "tools" in data
        assert "defaults" in data
        assert "features" in data

    def test_collect_widget_data_tools(self):
        """Test that tools section reflects configuration."""
        widget = AnnotationWidget(
            allow_text=True,
            allow_arrows=False,
            allow_circles=True,
            allow_rectangles=False,
        )
        data = widget.collect_widget_data()
        assert data["tools"]["text"] is True
        assert data["tools"]["arrow"] is False
        assert data["tools"]["circle"] is True
        assert data["tools"]["rectangle"] is False

    def test_collect_widget_data_defaults(self):
        """Test that defaults section contains styling config."""
        widget = AnnotationWidget(
            default_text_color="#FFFFFF",
            default_text_size=20,
            default_stroke_color="#00FF00",
            default_stroke_width=5,
            default_fill_opacity=0.5,
        )
        data = widget.collect_widget_data()
        assert data["defaults"]["text_color"] == "#FFFFFF"
        assert data["defaults"]["text_size"] == 20
        assert data["defaults"]["stroke_color"] == "#00FF00"
        assert data["defaults"]["stroke_width"] == 5
        assert data["defaults"]["fill_opacity"] == 0.5

    def test_collect_widget_data_features(self):
        """Test that features section reflects export/import/snap config."""
        widget = AnnotationWidget(
            enable_export=False,
            enable_import=False,
            snap_to_points=True,
            snap_distance=50,
        )
        data = widget.collect_widget_data()
        assert data["features"]["export"] is False
        assert data["features"]["import"] is False
        assert data["features"]["snap_to_points"] is True
        assert data["features"]["snap_distance"] == 50

    def test_initial_annotations(self):
        """Test annotation widget with initial annotations."""
        annotations = [
            {"type": "text", "x": 0, "y": 0, "content": "Hello"},
            {"type": "arrow", "x1": 0, "y1": 0, "x2": 1, "y2": 1},
        ]
        widget = AnnotationWidget(initial_annotations=annotations)
        assert widget.initial_annotations == annotations
        data = widget.collect_widget_data()
        assert data["initial_annotations"] == annotations

    def test_dependencies(self):
        """Test that annotation widget declares correct dependencies."""
        widget = AnnotationWidget()
        assert "js:annotation" in widget.dependencies
        assert "css:annotation" in widget.dependencies

    def test_html_output(self):
        """Test that HTML contains annotation container."""
        widget = AnnotationWidget()
        html = widget.html
        assert widget.get_container_id() in html
        assert "annotation-container" in html

    def test_javascript_output(self):
        """Test that JS output references AnnotationWidget."""
        widget = AnnotationWidget()
        js = widget.javascript
        assert "AnnotationWidget" in js
        assert widget.get_container_id() in js


# ============================================================
# Helper function tests
# ============================================================


class TestCollectWidgetData:
    """Tests for the collect_widget_data helper function."""

    def test_empty_widgets(self):
        """Test collecting data from widgets with no special data."""
        widgets = [TitleWidget(title="Test"), LegendWidget()]
        data = collect_widget_data(widgets)
        assert data["histograms"] == []
        assert data["colormaps"] == []
        assert data["search_fields"] == []

    def test_histogram_data_collected(self):
        """Test that histogram widget data is collected."""
        hist_data = [1.0, 2.0, 3.0, 4.0, 5.0]
        widget = HistogramWidget(histogram_data=hist_data)
        data = collect_widget_data([widget])
        assert len(data["histograms"]) == 1
        assert data["histograms"][0]["widget_id"] == "d3histogram"
        assert data["histograms"][0]["data"] == hist_data
        assert "settings" in data["histograms"][0]

    def test_histogram_data_not_collected_when_none(self):
        """Test that histogram with no data is not collected."""
        widget = HistogramWidget()  # histogram_data=None by default
        data = collect_widget_data([widget])
        assert data["histograms"] == []

    def test_colormap_data_collected(self):
        """Test that colormap selector metadata is collected."""
        metadata = [{"name": "viridis", "type": "sequential"}]
        widget = ColormapSelectorWidget(colormap_metadata=metadata)
        data = collect_widget_data([widget])
        assert len(data["colormaps"]) == 1
        assert data["colormaps"][0]["widget_id"] == "colormap-selector"
        assert data["colormaps"][0]["available_colormaps"] == metadata

    def test_colormap_data_not_collected_when_none(self):
        """Test that colormap selector with no metadata is not collected."""
        widget = ColormapSelectorWidget()
        data = collect_widget_data([widget])
        assert data["colormaps"] == []

    def test_search_field_collected(self):
        """Test that search widget field is collected."""
        widget = SearchWidget(search_field="description")
        data = collect_widget_data([widget])
        assert len(data["search_fields"]) == 1
        assert data["search_fields"][0]["search_field"] == "description"

    def test_mixed_widgets(self):
        """Test collecting data from multiple widget types."""
        widgets = [
            TitleWidget(title="Test"),
            SearchWidget(search_field="content"),
            HistogramWidget(histogram_data=[1, 2, 3]),
            ColormapSelectorWidget(colormap_metadata=[{"name": "viridis"}]),
            LegendWidget(),
        ]
        data = collect_widget_data(widgets)
        assert len(data["histograms"]) == 1
        assert len(data["colormaps"]) == 1
        assert len(data["search_fields"]) == 1

    def test_multiple_histograms(self):
        """Test collecting data from multiple histogram widgets."""
        w1 = HistogramWidget(histogram_data=[1, 2, 3], widget_id="hist1")
        w2 = HistogramWidget(histogram_data=[4, 5, 6], widget_id="hist2")
        data = collect_widget_data([w1, w2])
        assert len(data["histograms"]) == 2
        widget_ids = [h["widget_id"] for h in data["histograms"]]
        assert "hist1" in widget_ids
        assert "hist2" in widget_ids


class TestLegacyWidgetFlags:
    """Tests for the legacy_widget_flags_from_widgets helper function."""

    def test_no_widgets(self):
        """Test with empty widget list."""
        result = legacy_widget_flags_from_widgets([])
        (
            enable_search,
            enable_histogram,
            enable_topic_tree,
            search_field,
            histogram_ctx,
            topic_tree_kwds,
        ) = result
        assert enable_search is False
        assert enable_histogram is False
        assert enable_topic_tree is False
        assert search_field == "hover_text"
        assert histogram_ctx == {}
        assert topic_tree_kwds == {}

    def test_with_search_widget(self):
        """Test that SearchWidget sets enable_search=True."""
        widgets = [SearchWidget(search_field="title")]
        result = legacy_widget_flags_from_widgets(widgets)
        assert result[0] is True  # enable_search
        assert result[3] == "title"  # search_field

    def test_with_histogram_widget(self):
        """Test that HistogramWidget sets enable_histogram=True."""
        data = [1.0, 2.0, 3.0]
        widgets = [HistogramWidget(histogram_data=data, histogram_width=400)]
        result = legacy_widget_flags_from_widgets(widgets)
        assert result[1] is True  # enable_histogram
        assert result[4]["histogram_data"] == data
        assert result[4]["histogram_settings"]["histogram_width"] == 400

    def test_with_topic_tree(self):
        """Test that TopicTreeWidget sets enable_topic_tree=True."""
        widgets = [TopicTreeWidget(title="My Tree", font_size="14pt")]
        result = legacy_widget_flags_from_widgets(widgets)
        assert result[2] is True  # enable_topic_tree

    def test_with_mixed_widgets(self):
        """Test with multiple widget types."""
        widgets = [
            TitleWidget(title="Test"),
            SearchWidget(),
            HistogramWidget(histogram_data=[1, 2]),
        ]
        result = legacy_widget_flags_from_widgets(widgets)
        assert result[0] is True  # enable_search
        assert result[1] is True  # enable_histogram
        assert result[2] is False  # enable_topic_tree


class TestUpdateDrawerEnabledForHandlers:
    """Tests for the update_drawer_enabled_for_handlers helper function."""

    def test_no_handlers(self):
        """Test that None handlers returns drawer_enabled unchanged."""
        drawer_enabled = {"left": False, "right": False, "bottom": False}
        result = update_drawer_enabled_for_handlers(drawer_enabled, None)
        assert result["left"] is False
        assert result["right"] is False
        assert result["bottom"] is False

    def test_handler_enables_left_drawer(self):
        """Test that a handler with left-drawer location enables left drawer."""
        from datamapplot.selection_handlers import SelectionHandlerBase

        handler = SelectionHandlerBase(location="left-drawer")
        drawer_enabled = {"left": False, "right": False, "bottom": False}
        result = update_drawer_enabled_for_handlers(drawer_enabled, handler)
        assert result["left"] is True
        assert result["right"] is False

    def test_handler_enables_right_drawer(self):
        """Test that a handler with right-drawer location enables right drawer."""
        from datamapplot.selection_handlers import SelectionHandlerBase

        handler = SelectionHandlerBase(location="right-drawer")
        drawer_enabled = {"left": False, "right": False, "bottom": False}
        result = update_drawer_enabled_for_handlers(drawer_enabled, handler)
        assert result["right"] is True
        assert result["left"] is False

    def test_handler_enables_bottom_drawer(self):
        """Test that a handler with bottom-drawer location enables bottom drawer."""
        from datamapplot.selection_handlers import SelectionHandlerBase

        handler = SelectionHandlerBase(location="bottom-drawer")
        drawer_enabled = {"left": False, "right": False, "bottom": False}
        result = update_drawer_enabled_for_handlers(drawer_enabled, handler)
        assert result["bottom"] is True

    def test_handler_list(self):
        """Test with a list of handlers enabling different drawers."""
        from datamapplot.selection_handlers import SelectionHandlerBase

        handlers = [
            SelectionHandlerBase(location="left-drawer"),
            SelectionHandlerBase(location="right-drawer"),
        ]
        drawer_enabled = {"left": False, "right": False, "bottom": False}
        result = update_drawer_enabled_for_handlers(drawer_enabled, handlers)
        assert result["left"] is True
        assert result["right"] is True
        assert result["bottom"] is False

    def test_does_not_mutate_input(self):
        """Test that the input dictionary is not mutated."""
        from datamapplot.selection_handlers import SelectionHandlerBase

        handler = SelectionHandlerBase(location="left-drawer")
        drawer_enabled = {"left": False, "right": False, "bottom": False}
        result = update_drawer_enabled_for_handlers(drawer_enabled, handler)
        assert drawer_enabled["left"] is False  # Original unchanged
        assert result["left"] is True

    def test_empty_handler_list(self):
        """Test with an empty list of handlers."""
        drawer_enabled = {"left": False, "right": False, "bottom": False}
        result = update_drawer_enabled_for_handlers(drawer_enabled, [])
        assert result["left"] is False
        assert result["right"] is False

    def test_preserves_existing_true_state(self):
        """Test that existing True drawer states are preserved."""
        from datamapplot.selection_handlers import SelectionHandlerBase

        handler = SelectionHandlerBase(location="right-drawer")
        drawer_enabled = {"left": True, "right": False, "bottom": False}
        result = update_drawer_enabled_for_handlers(drawer_enabled, handler)
        assert result["left"] is True  # Preserved
        assert result["right"] is True  # Newly enabled


class TestWidgetDependencyParsing:
    """Tests for dependency format parsing in collect_widget_dependencies."""

    def test_js_prefix_format(self):
        """Test js: prefixed dependency routes to js_files."""
        widget = WidgetBase(widget_id="test", dependencies=["js:histogram"])
        deps = collect_widget_dependencies([widget])
        assert "histogram" in deps["js_files"]
        assert len(deps["css_files"]) == 0
        assert len(deps["external_js"]) == 0

    def test_css_prefix_format(self):
        """Test css: prefixed dependency routes to css_files."""
        widget = WidgetBase(widget_id="test", dependencies=["css:histogram"])
        deps = collect_widget_dependencies([widget])
        assert "histogram" in deps["css_files"]
        assert len(deps["js_files"]) == 0

    def test_external_url_js(self):
        """Test http/https URL routes to external_js."""
        widget = WidgetBase(
            widget_id="test",
            dependencies=["https://cdn.example.com/d3.v7.min.js"],
        )
        deps = collect_widget_dependencies([widget])
        assert "https://cdn.example.com/d3.v7.min.js" in deps["external_js"]
        assert len(deps["js_files"]) == 0

    def test_external_url_css(self):
        """Test external CSS URL routes to css_files (without extension)."""
        widget = WidgetBase(
            widget_id="test",
            dependencies=["https://cdn.example.com/style.css"],
        )
        deps = collect_widget_dependencies([widget])
        # External CSS URLs go to external_js (treated as external dep) since they start with https
        assert "https://cdn.example.com/style.css" in deps["external_js"]

    def test_legacy_js_extension(self):
        """Test legacy .js extension format strips extension."""
        widget = WidgetBase(widget_id="test", dependencies=["d3.js"])
        deps = collect_widget_dependencies([widget])
        assert "d3" in deps["js_files"]

    def test_legacy_css_extension(self):
        """Test legacy .css extension format strips extension."""
        widget = WidgetBase(widget_id="test", dependencies=["style.css"])
        deps = collect_widget_dependencies([widget])
        assert "style" in deps["css_files"]

    def test_real_widget_dependencies(self):
        """Test dependency parsing with real widget classes."""
        widgets = [
            TopicTreeWidget(),
            HistogramWidget(),
            SelectionControlWidget(),
            MiniMapWidget(),
        ]
        deps = collect_widget_dependencies(widgets)
        assert "topic_tree" in deps["js_files"]
        assert "topic_tree" in deps["css_files"]
        assert "d3" in deps["js_files"]
        assert "histogram" in deps["js_files"]
        assert "histogram" in deps["css_files"]
        assert "selection_control" in deps["js_files"]
        assert "selection_control" in deps["css_files"]
        assert "minimap" in deps["js_files"]
        assert "minimap" in deps["css_files"]

    def test_no_dependencies(self):
        """Test widgets with empty dependency lists."""
        widgets = [TitleWidget(title="Test"), LogoWidget(logo="test.png")]
        deps = collect_widget_dependencies(widgets)
        assert len(deps["js_files"]) == 0
        assert len(deps["css_files"]) == 0
        assert len(deps["external_js"]) == 0


# ============================================================
# Edge cases and parametrized tests
# ============================================================


class TestWidgetEdgeCases:
    """Tests for widget edge cases and cross-cutting concerns."""

    def test_duplicate_widget_ids_both_present(self):
        """Test that duplicate widget IDs are both included in grouping."""
        w1 = TitleWidget(title="First", widget_id="title")
        w2 = TitleWidget(title="Second", widget_id="title")
        grouped = group_widgets_by_location([w1, w2])
        assert len(grouped["top-left"]) == 2

    def test_all_valid_locations_accepted(self):
        """Test that WidgetBase accepts all valid locations."""
        for loc in VALID_LOCATIONS:
            widget = WidgetBase(widget_id="test", location=loc)
            assert widget.location == loc

    def test_invalid_location_on_widget_config(self):
        """Test that WidgetConfig with invalid location raises ValueError."""
        with pytest.raises(ValueError, match="Invalid location"):
            WidgetConfig(widget_id="test", location="center")

    @pytest.mark.parametrize(
        "widget_cls,kwargs",
        [
            (WidgetBase, {"widget_id": "test"}),
            (TitleWidget, {"title": "Test"}),
            (SearchWidget, {}),
            (TopicTreeWidget, {}),
            (HistogramWidget, {}),
            (ColormapSelectorWidget, {}),
            (LegendWidget, {}),
            (LogoWidget, {"logo": "test.png"}),
            (SelectionControlWidget, {}),
            (LayerToggleWidget, {}),
            (MiniMapWidget, {}),
            (RESTSearchWidget, {"endpoint_url": "https://example.com/search"}),
            (AnnotationWidget, {}),
        ],
    )
    def test_render_returns_dict(self, widget_cls, kwargs):
        """Test that render() returns dict with html, css, javascript keys."""
        widget = widget_cls(**kwargs)
        result = widget.render()
        assert isinstance(result, dict)
        assert "html" in result
        assert "css" in result
        assert "javascript" in result

    @pytest.mark.parametrize(
        "widget_cls,kwargs",
        [
            (WidgetBase, {"widget_id": "test"}),
            (TitleWidget, {"title": "Test"}),
            (SearchWidget, {}),
            (TopicTreeWidget, {}),
            (HistogramWidget, {}),
            (ColormapSelectorWidget, {}),
            (LegendWidget, {}),
            (LogoWidget, {"logo": "test.png"}),
            (SelectionControlWidget, {}),
            (LayerToggleWidget, {}),
            (MiniMapWidget, {}),
            (RESTSearchWidget, {"endpoint_url": "https://example.com/search"}),
            (AnnotationWidget, {}),
        ],
    )
    def test_get_config_keys(self, widget_cls, kwargs):
        """Test that get_config() returns dict with required keys."""
        widget = widget_cls(**kwargs)
        config = widget.get_config()
        assert "widget_id" in config
        assert "location" in config
        assert "order" in config
        assert "visible" in config
        assert "collapsible" in config

    @pytest.mark.parametrize(
        "widget_cls,kwargs",
        [
            (TitleWidget, {"title": "Test"}),
            (SearchWidget, {}),
            (TopicTreeWidget, {}),
            (HistogramWidget, {}),
            (ColormapSelectorWidget, {}),
            (LegendWidget, {}),
            (LogoWidget, {"logo": "test.png"}),
            (SelectionControlWidget, {}),
            (LayerToggleWidget, {}),
            (MiniMapWidget, {}),
            (RESTSearchWidget, {"endpoint_url": "https://example.com/search"}),
            (AnnotationWidget, {}),
        ],
    )
    def test_html_is_string(self, widget_cls, kwargs):
        """Test that html property returns a non-empty string."""
        widget = widget_cls(**kwargs)
        html = widget.html
        assert isinstance(html, str)
        assert len(html) > 0

    @pytest.mark.parametrize(
        "widget_cls,kwargs",
        [
            (TitleWidget, {"title": "Test"}),
            (SearchWidget, {}),
            (TopicTreeWidget, {}),
            (HistogramWidget, {}),
            (ColormapSelectorWidget, {}),
            (LegendWidget, {}),
            (LogoWidget, {"logo": "test.png"}),
            (SelectionControlWidget, {}),
            (LayerToggleWidget, {}),
            (MiniMapWidget, {}),
            (RESTSearchWidget, {"endpoint_url": "https://example.com/search"}),
            (AnnotationWidget, {}),
        ],
    )
    def test_container_id_format(self, widget_cls, kwargs):
        """Test that container ID follows '{widget_id}-container' pattern."""
        widget = widget_cls(**kwargs)
        assert widget.get_container_id() == f"{widget.widget_id}-container"

    def test_widget_order_sorting(self):
        """Test that widgets of different types sort correctly by order."""
        widgets = [
            SearchWidget(order=3),
            TitleWidget(title="T", order=1),
            LegendWidget(order=2),
        ]
        grouped = group_widgets_by_location(widgets)
        top_left = grouped["top-left"]
        # TitleWidget(order=1) and SearchWidget(order=3) are both top-left
        assert top_left[0].order <= top_left[1].order

    def test_widget_config_custom_params_in_factory(self):
        """Test that WidgetConfig custom_params are passed to the widget."""
        config = WidgetConfig(
            widget_id="title",
            location="drawer-right",
            order=5,
            custom_params={"title": "Custom Title"},
        )
        widget = create_widget_from_config("title", config=config)
        assert widget.location == "drawer-right"
        assert widget.order == 5
        assert widget.title_text == "Custom Title"


class TestWidgetConfigPresets:
    """Tests for loading widget configuration presets."""

    @pytest.fixture
    def config_dir(self):
        """Return the path to the widget_configs directory."""
        return Path(__file__).parent.parent / "widget_configs"

    def _load_preset(self, path):
        """Load a preset JSON file, stripping non-widget metadata keys."""
        with open(path, "r") as f:
            raw = json.load(f)
        # Filter out metadata keys like _description
        config_dict = {k: v for k, v in raw.items() if not k.startswith("_")}
        configs = {}
        for widget_id, config in config_dict.items():
            config["widget_id"] = widget_id
            configs[widget_id] = WidgetConfig(**config)
        return configs

    def test_load_default_preset(self, config_dir):
        """Test loading the default configuration preset."""
        configs = self._load_preset(config_dir / "default.json")
        assert isinstance(configs, dict)
        assert "title" in configs
        assert "search" in configs

    def test_load_minimal_preset(self, config_dir):
        """Test loading the minimal configuration preset."""
        configs = self._load_preset(config_dir / "minimal.json")
        assert isinstance(configs, dict)
        # Minimal should have fewer widgets
        assert len(configs) <= 3

    def test_load_analyst_preset(self, config_dir):
        """Test loading the analyst configuration preset with drawer locations."""
        configs = self._load_preset(config_dir / "analyst.json")
        assert isinstance(configs, dict)
        # Analyst preset should use drawer locations for some widgets
        drawer_locations = [
            c.location for c in configs.values() if c.location.startswith("drawer-")
        ]
        assert len(drawer_locations) > 0

    def test_load_presentation_preset(self, config_dir):
        """Test loading the presentation configuration preset."""
        configs = self._load_preset(config_dir / "presentation.json")
        assert isinstance(configs, dict)
        assert "title" in configs

    def test_all_presets_have_valid_locations(self, config_dir):
        """Test that all presets only use valid locations."""
        for preset_file in config_dir.glob("*.json"):
            configs = self._load_preset(preset_file)
            for widget_id, config in configs.items():
                assert config.location in VALID_LOCATIONS, (
                    f"Preset '{preset_file.name}', widget '{widget_id}' "
                    f"has invalid location '{config.location}'"
                )


class TestCreateWidgetFromConfigExtended:
    """Extended tests for the widget factory function."""

    @pytest.mark.parametrize(
        "widget_type,expected_cls",
        [
            ("title", TitleWidget),
            ("search", SearchWidget),
            ("topic_tree", TopicTreeWidget),
            ("histogram", HistogramWidget),
            ("colormap_selector", ColormapSelectorWidget),
            ("legend", LegendWidget),
            ("logo", LogoWidget),
            ("selection_control", SelectionControlWidget),
            ("layer_toggle", LayerToggleWidget),
            ("minimap", MiniMapWidget),
            ("rest_search", RESTSearchWidget),
            ("annotation", AnnotationWidget),
        ],
    )
    def test_create_all_widget_types(self, widget_type, expected_cls):
        """Test that factory creates the correct widget class for each type."""
        # Provide required args for widgets that need them
        extra_kwargs = {}
        if widget_type == "title":
            extra_kwargs["title"] = "Test"
        elif widget_type == "logo":
            extra_kwargs["logo"] = "test.png"
        elif widget_type == "rest_search":
            extra_kwargs["endpoint_url"] = "https://example.com/search"

        widget = create_widget_from_config(widget_type, **extra_kwargs)
        assert isinstance(widget, expected_cls)

    def test_factory_with_location_override(self):
        """Test that factory applies location from WidgetConfig."""
        config = WidgetConfig(
            widget_id="search",
            location="drawer-right",
            order=10,
        )
        widget = create_widget_from_config("search", config=config)
        assert widget.location == "drawer-right"
        assert widget.order == 10
