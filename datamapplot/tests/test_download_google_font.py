import itertools
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from datamapplot import rendering_helpers


def _font(content=b"ttf bytes"):
    font = MagicMock()
    font.fetch.return_value = content
    return font


def _fake_temp_files():
    for index in itertools.count():
        temp_file = MagicMock()
        temp_file.name = f"font-{index}.ttf"
        yield temp_file


@contextmanager
def _fake_font_manager(fonts):
    ttflist = []
    font_manager = rendering_helpers.font_manager.fontManager
    with patch.object(
        rendering_helpers, "query_google_fonts", return_value=fonts
    ) as query, patch.object(
        rendering_helpers, "NamedTemporaryFile", side_effect=_fake_temp_files()
    ), patch.object(font_manager, "ttflist", ttflist), patch.object(
        font_manager,
        "addfont",
        side_effect=lambda path: ttflist.append(SimpleNamespace(fname=path)),
    ):
        yield query, ttflist


def test_registered_font_is_not_downloaded_again():
    with _fake_font_manager([_font(), _font()]) as (query, ttflist):
        rendering_helpers.download_google_font("Cached Test Font")
        rendering_helpers.download_google_font("Cached Test Font")

    assert query.call_count == 1
    assert len(ttflist) == 2


def test_font_is_downloaded_again_after_font_list_rebuild():
    with _fake_font_manager([_font()]) as (query, ttflist):
        rendering_helpers.download_google_font("Rebuilt Test Font")
        ttflist.clear()
        rendering_helpers.download_google_font("Rebuilt Test Font")

    assert query.call_count == 2
    assert len(ttflist) == 1


def test_failed_font_download_is_retried():
    with _fake_font_manager([]) as (query, _):
        rendering_helpers.download_google_font("Unreachable Test Font")
        rendering_helpers.download_google_font("Unreachable Test Font")

    assert query.call_count == 2
