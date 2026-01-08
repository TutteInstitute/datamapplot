"""Tests for the widget system."""

import pytest
import json
import tempfile
from pathlib import Path

from datamapplot.widgets import (
    WidgetBase,
    TitleWidget,
    SearchWidget,
    TopicTreeWidget,
    HistogramWidget,
    ColormapSelectorWidget,
    LegendWidget,
    LogoWidget,
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
        assert deps["js"] == []
        assert deps["css"] == []

    def test_collect_with_dependencies(self):
        """Test collecting from widget with dependencies."""
        widget = WidgetBase(
            widget_id="test",
            dependencies=[
                "https://example.com/lib.js",
                "https://example.com/style.css",
            ],
        )
        deps = collect_widget_dependencies([widget])
        assert "https://example.com/lib.js" in deps["js"]
        assert "https://example.com/style.css" in deps["css"]

    def test_collect_no_duplicates(self):
        """Test that duplicate dependencies are removed."""
        widget1 = WidgetBase(
            widget_id="w1", dependencies=["https://example.com/lib.js"]
        )
        widget2 = WidgetBase(
            widget_id="w2", dependencies=["https://example.com/lib.js"]
        )
        deps = collect_widget_dependencies([widget1, widget2])
        assert len(deps["js"]) == 1


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
