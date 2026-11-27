"""Widget gallery: every built-in widget in one plot, for reviewing widget styles.

Writes two pages built from the same synthetic data map, so that widget styles
can be compared across themes and fonts:

* ``widget_gallery_light.html``: light mode, in Roboto;
* ``widget_gallery_dark.html``: dark mode, in Playfair Display.

Each page has a widget in every corner, more in the left and right drawers, and
a selection handler (its panel appears in the right drawer after a lasso
selection). The Playwright spec ``tests/widget_gallery.spec.ts`` snapshots them.

    python datamapplot/interactive_tests/widget_gallery.py [OUTPUT_DIR]
"""

import base64
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import datamapplot
from datamapplot.selection_handlers import DisplaySample

FIELDS = {
    "Astronomy": ["Exoplanets", "Galaxies", "Cosmology", "Solar Physics"],
    "Biology": ["Genomics", "Ecology", "Neuroscience", "Immunology"],
    "Chemistry": ["Catalysis", "Polymers", "Spectroscopy"],
    "Economics": ["Labour Markets", "Trade", "Monetary Policy"],
    "History": ["Ancient Rome", "Medieval Europe", "Industrial Revolution"],
}

THEMES = {
    "light": {"darkmode": False, "font_family": "Roboto"},
    "dark": {"darkmode": True, "font_family": "Playfair Display"},
}

_LOGO_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="240" height="80" viewBox="0 0 240 80">'
    '<rect x="2" y="2" width="236" height="76" rx="16" fill="#3ba5e7"/>'
    '<text x="120" y="52" font-family="sans-serif" font-size="32" font-weight="bold" '
    'fill="white" text-anchor="middle">Gallery</text></svg>'
)
LOGO = "data:image/svg+xml;base64," + base64.b64encode(_LOGO_SVG.encode()).decode()


def synthetic_data(n=3000, seed=0):
    """A clustered data map with two label layers, hover text and metadata."""
    rng = np.random.default_rng(seed)
    topics = [(field, topic) for field, subtopics in FIELDS.items() for topic in subtopics]
    field_centres = {field: rng.uniform(-10, 10, size=2) for field in FIELDS}
    topic_index = rng.integers(len(topics), size=n)
    centres = np.array(
        [field_centres[field] + rng.normal(scale=2.5, size=2) for field, _ in topics]
    )
    data_map = centres[topic_index] + rng.normal(scale=0.7, size=(n, 2))
    fine = np.array([topics[i][1] for i in topic_index], dtype=object)
    coarse = np.array([topics[i][0] for i in topic_index], dtype=object)
    # Some points are unclustered, as in real data maps.
    noise = rng.random(n) < 0.08
    fine[noise] = "Unlabelled"
    coarse[noise & (rng.random(n) < 0.5)] = "Unlabelled"
    hover_text = np.array(
        [f"Paper {i}: a study in {fine[i].lower()}" for i in range(n)], dtype=object
    )
    published = pd.Series(
        pd.to_datetime("2015-01-01")
        + pd.to_timedelta(rng.integers(0, 365 * 10, size=n), unit="D")
    )
    citations = np.round(rng.lognormal(mean=2.0, sigma=1.2, size=n))
    return data_map, [fine, coarse], hover_text, published, coarse, citations


def gallery_widgets(published, coarse, citations):
    """One of every built-in widget, spread over the corners and drawers."""
    return [
        datamapplot.TitleWidget(
            title="Widget Gallery",
            sub_title="Every DataMapPlot widget on one map",
        ),
        datamapplot.SearchWidget(),
        datamapplot.TopicTreeWidget(max_height="30vh"),
        datamapplot.LegendWidget(),
        datamapplot.LayerToggleWidget(),
        datamapplot.ColormapSelectorWidget(
            colormaps={
                "Field": coarse,
                "Citations": citations,
                "Year": published.dt.year.values,
            }
        ),
        datamapplot.HistogramWidget(
            histogram_data=published, histogram_title="Published"
        ),
        datamapplot.MiniMapWidget(),
        datamapplot.LogoWidget(logo=LOGO, logo_width=120),
        datamapplot.AnnotationWidget(),
        datamapplot.RESTSearchWidget(endpoint_url="http://127.0.0.1:9/search"),
        datamapplot.SelectionControlWidget(location="drawer-right", order=0),
    ]


def build_gallery(output_dir=".", themes=THEMES):
    """Write one gallery page per theme to ``output_dir``; returns their paths."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    data_map, labels, hover_text, published, coarse, citations = synthetic_data()
    paths = []
    for name, theme in themes.items():
        plot = datamapplot.create_interactive_plot(
            data_map,
            *labels,
            hover_text=hover_text,
            widgets=gallery_widgets(published, coarse, citations),
            selection_handler=DisplaySample(n_samples=8),
            initial_zoom_fraction=0.9,
            **theme,
        )
        path = output_dir / f"widget_gallery_{name}.html"
        plot.save(str(path))
        paths.append(path)
    return paths


if __name__ == "__main__":
    for path in build_gallery(sys.argv[1] if len(sys.argv) > 1 else "."):
        print(path)
