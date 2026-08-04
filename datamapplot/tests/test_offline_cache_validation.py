"""Tests for offline cache coverage checks (issue #205).

The offline cache is keyed by exact dependency URL, so a cache built by an
older version of DataMapPlot silently stops satisfying a dependency whose URL
has since changed. Before these checks the only symptom was a ``console.error``
in the browser and a plot stuck on its loading screen.
"""

import json
import tempfile
import unittest
import warnings
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import numpy as np

import datamapplot
from datamapplot import offline_mode_caching
from datamapplot.interactive_helpers import (
    get_google_font_for_embedding,
    prepare_fonts,
    prepare_offline_mode_data,
)
from datamapplot.offline_mode_caching import (
    OfflineCacheError,
    check_css_cache_coverage,
    check_js_cache_coverage,
    missing_cache_entries,
)

# The deck.gl URL as it was before it got pinned in 0.7.3 (PR #193). A cache
# built by 0.7.2 or earlier is keyed on this and has no entry for the pinned
# URL that 0.7.3 asks for.
UNPINNED_DECKGL_URL = "https://unpkg.com/deck.gl@latest/dist.min.js"
PINNED_DECKGL_URL = "https://unpkg.com/deck.gl@9.1/dist.min.js"


@contextmanager
def user_warnings_recorded():
    """Capture UserWarnings, since ``assertWarns`` has no negative counterpart."""
    caught = []
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        yield caught
    caught.extend(
        str(w.message) for w in recorded if issubclass(w.category, UserWarning)
    )


def _fake_cache_entry(url):
    return {
        "encoded_content": "Y29udGVudA==",
        "name": "".join(c if c.isalnum() else "_" for c in url),
    }


def _js_cache(urls):
    return {url: _fake_cache_entry(url) for url in urls}


def _current_js_cache():
    """A cache with an entry for every dependency this version can ask for."""
    return _js_cache(offline_mode_caching.DEFAULT_URLS)


def _stale_js_cache():
    """A cache as an older DataMapPlot would have built it."""
    urls = [
        UNPINNED_DECKGL_URL if url == PINNED_DECKGL_URL else url
        for url in offline_mode_caching.DEFAULT_URLS
    ]
    return _js_cache(urls)


FONT_CACHE = {
    "Roboto": [
        {
            "style": "normal",
            "weight": "400",
            "unicode_range": "",
            "type": "ttf",
            "content": "Um9ib3RvRm9udENvbnRlbnQ=",
        }
    ]
}


class TestMissingCacheEntries(unittest.TestCase):
    """The primitive the checks are built on."""

    def test_reports_absent_urls_in_order(self):
        cache = _js_cache(["https://a", "https://c"])
        self.assertEqual(
            missing_cache_entries(cache, ["https://a", "https://b", "https://d"]),
            ["https://b", "https://d"],
        )

    def test_full_cache_reports_nothing(self):
        cache = _js_cache(["https://a", "https://b"])
        self.assertEqual(missing_cache_entries(cache, ["https://a"]), [])

    def test_empty_cache_reports_everything(self):
        for cache in ({}, None):
            with self.subTest(cache=cache):
                self.assertEqual(
                    missing_cache_entries(cache, ["https://a", "https://b"]),
                    ["https://a", "https://b"],
                )


class TestJsCacheCoverage(unittest.TestCase):
    """Missing JavaScript is fatal: the plot cannot load without it."""

    def test_complete_cache_passes(self):
        cache = _current_js_cache()
        check_js_cache_coverage(cache, offline_mode_caching.DEFAULT_URLS)

    def test_missing_url_raises(self):
        with self.assertRaises(OfflineCacheError) as ctx:
            check_js_cache_coverage(_stale_js_cache(), [PINNED_DECKGL_URL])
        self.assertEqual(ctx.exception.missing_urls, [PINNED_DECKGL_URL])

    def test_error_message_is_actionable(self):
        with self.assertRaises(OfflineCacheError) as ctx:
            check_js_cache_coverage(
                _stale_js_cache(),
                [PINNED_DECKGL_URL],
                cache_file="/somewhere/datamapplot_js_encoded.json",
            )
        message = str(ctx.exception)
        # Names the dependency, where the cache lives, and how to fix it.
        self.assertIn(PINNED_DECKGL_URL, message)
        self.assertIn("/somewhere/datamapplot_js_encoded.json", message)
        self.assertIn("dmp_offline_cache --refresh", message)
        self.assertIn("dmp_offline_cache --export", message)

    def test_message_counts_multiple_missing_urls(self):
        with self.assertRaises(OfflineCacheError) as ctx:
            check_js_cache_coverage({}, ["https://a", "https://b"])
        self.assertIn(
            "2 required JavaScript dependencies are missing", str(ctx.exception)
        )


class TestCssCacheCoverage(unittest.TestCase):
    """Missing CSS only costs styling, so it warns rather than raising."""

    def test_complete_cache_is_silent(self):
        cache = _js_cache(offline_mode_caching.DEFAULT_CSS_URLS)
        with user_warnings_recorded() as caught:
            check_css_cache_coverage(cache, offline_mode_caching.DEFAULT_CSS_URLS)
        self.assertEqual(caught, [])

    def test_missing_url_warns(self):
        css_url = "https://cdn.datatables.net/1.13.8/css/jquery.dataTables.min.css"
        with self.assertWarns(UserWarning) as ctx:
            check_css_cache_coverage({}, [css_url])
        message = str(ctx.warning)
        self.assertIn(css_url, message)
        self.assertIn("dmp_offline_cache --refresh", message)


class TestPrepareOfflineModeData(unittest.TestCase):
    """The checks as wired into the render path."""

    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.data_directory = Path(self._temp_dir.name)
        self.addCleanup(self._temp_dir.cleanup)

        # A complete CSS and font cache, so only the JS cache under test varies.
        self.write_cache(
            "datamapplot_css_encoded.json",
            _js_cache(offline_mode_caching.DEFAULT_CSS_URLS),
        )
        self.write_cache("datamapplot_fonts_encoded.json", FONT_CACHE)

        patcher = patch(
            "platformdirs.user_data_dir", return_value=str(self.data_directory)
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def write_cache(self, name, contents):
        path = self.data_directory / name
        with path.open("w") as f:
            json.dump(contents, f)
        return path

    def test_missing_js_dependency_raises(self):
        js_cache_file = self.write_cache(
            "datamapplot_js_encoded.json", _stale_js_cache()
        )
        with self.assertRaises(OfflineCacheError) as ctx:
            prepare_offline_mode_data(
                True,
                str(js_cache_file),
                None,
                js_dependency_urls=[PINNED_DECKGL_URL],
            )
        self.assertEqual(ctx.exception.missing_urls, [PINNED_DECKGL_URL])

    def test_complete_js_cache_passes(self):
        js_cache_file = self.write_cache(
            "datamapplot_js_encoded.json", _current_js_cache()
        )
        result = prepare_offline_mode_data(
            True,
            str(js_cache_file),
            None,
            js_dependency_urls=[PINNED_DECKGL_URL],
            css_dependency_urls=offline_mode_caching.DEFAULT_CSS_URLS,
        )
        self.assertIn(PINNED_DECKGL_URL, result["offline_mode_data"])

    def test_missing_css_dependency_warns_and_continues(self):
        js_cache_file = self.write_cache(
            "datamapplot_js_encoded.json", _current_js_cache()
        )
        css_url = "https://example.com/uncached.css"
        with self.assertWarns(UserWarning):
            result = prepare_offline_mode_data(
                True,
                str(js_cache_file),
                None,
                js_dependency_urls=[PINNED_DECKGL_URL],
                css_dependency_urls=[css_url],
            )
        self.assertIsNotNone(result["offline_mode_data"])

    def test_urls_are_optional(self):
        """Callers that pass no URLs get the previous unchecked behaviour."""
        js_cache_file = self.write_cache("datamapplot_js_encoded.json", {})
        result = prepare_offline_mode_data(True, str(js_cache_file), None)
        self.assertEqual(result["offline_mode_data"], {})

    def test_online_mode_is_unaffected(self):
        result = prepare_offline_mode_data(
            False, None, None, js_dependency_urls=[PINNED_DECKGL_URL]
        )
        self.assertIsNone(result["offline_mode_data"])


class TestInteractivePlotWithStaleCache(unittest.TestCase):
    """End-to-end: the failure reported in issue #205."""

    def setUp(self):
        np.random.seed(42)
        self.data_coords = np.random.randn(100, 2)
        self.labels = np.array(["Group A"] * 50 + ["Group B"] * 50)

        self._temp_dir = tempfile.TemporaryDirectory()
        self.data_directory = Path(self._temp_dir.name)
        self.addCleanup(self._temp_dir.cleanup)

        for name, contents in [
            (
                "datamapplot_css_encoded.json",
                _js_cache(offline_mode_caching.DEFAULT_CSS_URLS),
            ),
            ("datamapplot_fonts_encoded.json", FONT_CACHE),
        ]:
            with (self.data_directory / name).open("w") as f:
                json.dump(contents, f)

        patcher = patch(
            "platformdirs.user_data_dir", return_value=str(self.data_directory)
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def js_cache_file(self, contents):
        path = self.data_directory / "js_cache.json"
        with path.open("w") as f:
            json.dump(contents, f)
        return str(path)

    def test_stale_cache_raises_instead_of_rendering_a_broken_plot(self):
        with self.assertRaises(OfflineCacheError) as ctx:
            datamapplot.create_interactive_plot(
                self.data_coords,
                self.labels,
                offline_mode=True,
                offline_mode_js_data_file=self.js_cache_file(_stale_js_cache()),
            )
        self.assertIn(PINNED_DECKGL_URL, ctx.exception.missing_urls)

    def test_current_cache_still_renders(self):
        fig = datamapplot.create_interactive_plot(
            self.data_coords,
            self.labels,
            offline_mode=True,
            offline_mode_js_data_file=self.js_cache_file(_current_js_cache()),
        )
        self.assertIsInstance(fig, datamapplot.interactive_rendering.InteractiveFigure)


class TestOfflineFontHandling(unittest.TestCase):
    """Fonts degrade gracefully, but no longer silently."""

    def test_uncached_font_warns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            font_cache_path = Path(temp_dir) / "fonts.json"
            with font_cache_path.open("w") as f:
                json.dump(FONT_CACHE, f)

            with self.assertWarns(UserWarning) as ctx:
                result = get_google_font_for_embedding(
                    "Cinzel",
                    offline_mode=True,
                    offline_font_file=str(font_cache_path),
                )
            self.assertEqual(result, "")
            self.assertIn("Cinzel", str(ctx.warning))
            self.assertIn("dmp_offline_cache", str(ctx.warning))

    def test_cached_font_does_not_warn(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            font_cache_path = Path(temp_dir) / "fonts.json"
            with font_cache_path.open("w") as f:
                json.dump(FONT_CACHE, f)

            with user_warnings_recorded() as caught:
                result = get_google_font_for_embedding(
                    "Roboto",
                    offline_mode=True,
                    offline_font_file=str(font_cache_path),
                )
            self.assertIn("@font-face", result)
            self.assertEqual(caught, [])

    def test_tooltip_font_does_not_reach_out_to_google_fonts(self):
        """Offline mode must resolve the tooltip font from the cache alone."""
        with tempfile.TemporaryDirectory() as temp_dir:
            font_cache_path = Path(temp_dir) / "fonts.json"
            with font_cache_path.open("w") as f:
                json.dump(FONT_CACHE, f)

            with patch("requests.get", side_effect=AssertionError("network used")):
                result = prepare_fonts(
                    "Roboto",
                    "Roboto",
                    [],
                    True,
                    str(font_cache_path),
                )
            self.assertEqual(result["api_tooltip_fontname"], "Roboto")
            self.assertIn("@font-face", result["font_data"])


if __name__ == "__main__":
    unittest.main()
