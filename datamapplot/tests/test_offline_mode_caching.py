from copy import copy
from pathlib import Path
import pytest
import shutil
import subprocess as sp
from unittest.mock import patch

from ..offline_mode_caching import (
    _DATA_DIRECTORY,
    Cache,
    ConfirmInteractiveStdio,
    ConfirmYes,
    DEFAULT_CACHE_FILES,
    load_fonts,
    load_js_files,
    make_store
)


@pytest.fixture
def abcdefgh():
    return list("abcdefgh")


@pytest.mark.parametrize(
    "input,expected",
    [
        (["6"], {"f"}),
        (["2 8 5"], {"b", "e", "h"}),
        (["3-7"], {"c", "d", "e", "f", "g"}),
        (["2", "1-4"], {"a", "c", "d"}),
        (["2 1-4", "7 1 5"], {"c", "d", "e", "g"}),
        (["2 3.4", "5"], {"b", "c"}),
        (["a"], set("abcdefgh"))
    ]
)
def test_confirm_interactive(input, expected, abcdefgh):
    with patch("datamapplot.offline_mode_caching.input", side_effect=[*input, "."]):
        assert expected == ConfirmInteractiveStdio().confirm("Choose!", abcdefgh)


def test_confirm_yes(abcdefgh):
    assert set(abcdefgh) == ConfirmYes().confirm("", abcdefgh)


@pytest.fixture
def preserving_cache():
    dir = Path(_DATA_DIRECTORY)
    if dir.is_dir():
        try:
            backup = Cache.from_path(dir, ConfirmYes())
            yield None
        finally:
            backup.save()
    else:
        yield None


@pytest.fixture
def js_old():
    return {
        "https://unpkg.com/apache-arrow@latest/Arrow.es2015.min.js": {
            "encoded_content": "heyhey",
            "name": "arrow"
        },
        "https://unpkg.com/jquery@3.7.1/dist/jquery.min.js": {
            "encoded_content": "hoho",
            "name": "jquery"
        }
    }


@pytest.fixture
def js_new():
    return {
        "https://unpkg.com/d3@latest/dist/d3.min.js": {
            "encoded_content": "codecodecode",
            "name": "d3"
        },
        "https://unpkg.com/jquery@3.7.1/dist/jquery.min.js": {
            "encoded_content": "hoho",
            "name": "jquerynew"
        }
    }


@pytest.fixture
def fonts_old():
    return {
        "Roboto": [
            {
                "style": "normal",
                "type": "truetype",
                "weight": "100",
                "unicode_range": "",
                "content": "blaaaaah"
            },
            {
                "style": "italic",
                "type": "truetype",
                "weight": "400",
                "unicode_range": "",
                "content": "blooh"
            }
        ],
        "Marcellus": [
            {
                "style": "normal",
                "type": "truetype",
                "weight": "400",
                "unicode_range": "",
                "content": "tedious"
            }
        ]
    }


@pytest.fixture
def fonts_new():
    return {
        "Roboto": [
            {
                "style": "normal",
                "type": "truetype",
                "weight": "100",
                "unicode_range": "",
                "content": "blaaaaah"
            },
        ],
        "Marcellus SC": [
            {
                "style": "normal",
                "type": "truetype",
                "weight": "400",
                "unicode_range": "",
                "content": "probablythesameasmarcellus"
            }
        ]
     }


@pytest.fixture
def dir_cache(tmp_path):
    dir = tmp_path / "cache"
    dir.mkdir(parents=True, exist_ok=True)
    return dir


@pytest.fixture
def zip_cache(tmp_path):
    return tmp_path / "cache.zip"


@pytest.fixture
def cache_in_mem(js_old, fonts_old, dir_cache, zip_cache, request):
    name_confirm, name_cache = request.param
    return Cache(
        js=js_old,
        fonts=fonts_old,
        confirm={
            "yes": ConfirmYes,
            "interactive": ConfirmInteractiveStdio
        }[name_confirm](),
        store=make_store(
            {"dir": dir_cache, "zip": zip_cache}[name_cache]
        )
    )


@pytest.mark.parametrize(
    "cache_in_mem,validate_store",
    [(("yes", "dir"), Path.is_dir), (("yes", "zip"), Path.is_file)],
    indirect=["cache_in_mem"]
)
def test_store(cache_in_mem, validate_store):
    cache_in_mem.save()
    path_cache = cache_in_mem.store.path
    assert validate_store(path_cache)
    assert cache_in_mem == Cache.from_path(path_cache, ConfirmYes())


@pytest.fixture
def no_cache(preserving_cache):
    shutil.rmtree(Path(DEFAULT_CACHE_FILES["javascript"]).parent, ignore_errors=True)


@pytest.fixture
def path_archive(js_new, fonts_new, zip_cache):
    cache = Cache(
        js=js_new,
        fonts=fonts_new,
        confirm=ConfirmYes(),
        store=make_store(zip_cache)
    )
    cache.save()
    return zip_cache


def dmp_offline_cache(*args: str, input="", is_returncode_checked=True) -> int:
    cp = sp.run(
        ["dmp_offline_cache", "--no-refresh", *args],
        input=input,
        encoding="utf-8"
    )
    if is_returncode_checked:
        cp.check_returncode()
    return cp.returncode


def test_import_no_clobber(no_cache, path_archive, js_new, fonts_new):
    assert not Path(_DATA_DIRECTORY).is_dir()
    with pytest.raises(OSError):
        load_js_files()
    with pytest.raises(OSError):
        load_fonts()
    assert path_archive.is_file() and path_archive.suffix == ".zip"

    dmp_offline_cache("--import", str(path_archive))

    assert js_new == load_js_files()
    assert fonts_new == load_fonts()


@pytest.fixture
def existing_cache(preserving_cache, js_old, fonts_old):
    dir = Path(_DATA_DIRECTORY)
    dir.mkdir(parents=True, exist_ok=True)
    cache = Cache.from_path(dir, confirm=ConfirmYes())
    cache.js = js_old
    cache.fonts = fonts_old
    cache.save()
    return cache


def _merge(*dicts):
    merged = {}
    for d in dicts:
        merged.update(d)
    return merged


@pytest.fixture
def js_imported_full(js_old, js_new):
    return _merge(js_old, js_new)


@pytest.fixture
def fonts_imported_full(fonts_old, fonts_new):
    return _merge(fonts_old, fonts_new)


@pytest.mark.parametrize(
    "cache_in_mem",
    [("interactive", "zip")],
    indirect=["cache_in_mem"]
)
def test_update_clobber(
    cache_in_mem,
    path_archive,
    js_imported_full,
    fonts_imported_full
):
    cache_src = Cache.from_path(path_archive, ConfirmYes())
    with patch("datamapplot.offline_mode_caching.input", side_effect=["1-2 .", "1 ."]):
        cache_in_mem.update(cache_src)
    assert js_imported_full == cache_in_mem.js
    assert fonts_imported_full == cache_in_mem.fonts


def test_import_clobber_partial(
    existing_cache,
    path_archive,
    js_old,
    fonts_old,
    js_imported_full,
    fonts_new
):
    assert js_old == load_js_files()
    assert fonts_old == load_fonts()

    dmp_offline_cache("--import", str(path_archive), input="1-2 .\n.\n")

    assert js_imported_full == load_js_files()
    fonts_after = {}
    fonts_after.update(fonts_old)
    fonts_after["Marcellus SC"] = fonts_new["Marcellus SC"]
    assert fonts_after == load_fonts()


def test_import_no_confirm(
    existing_cache,
    path_archive,
    js_old,
    fonts_old,
    js_imported_full,
    fonts_imported_full
):
    assert js_old == load_js_files()
    assert fonts_old == load_fonts()

    dmp_offline_cache("--yes", "--import", str(path_archive), input="")

    assert js_imported_full == load_js_files()
    assert fonts_imported_full == load_fonts()


def test_export_no_clobber(existing_cache, zip_cache, js_old, fonts_old):
    assert not zip_cache.exists()
    dmp_offline_cache("--export", str(zip_cache), "--no-refresh")

    cache_exported = Cache.from_path(zip_cache, ConfirmYes())
    assert js_old == cache_exported.js
    assert fonts_old == cache_exported.fonts


@pytest.fixture
def js_exported_full(js_old, js_new):
    return _merge(js_new, js_old)


@pytest.fixture
def fonts_exported_full(fonts_old, fonts_new):
    return _merge(fonts_new, fonts_old)


def test_export_clobber_partial(
    existing_cache,
    path_archive,
    js_old,
    js_new,
    fonts_exported_full
):
    assert path_archive.is_file()
    dmp_offline_cache("--export", str(path_archive), "--no-refresh", input=".\na.\n")

    cache_exported = Cache.from_path(path_archive, ConfirmYes())
    js_expected = {}
    js_expected.update(js_new)
    js_expected["https://unpkg.com/apache-arrow@latest/Arrow.es2015.min.js"] = js_old[
        "https://unpkg.com/apache-arrow@latest/Arrow.es2015.min.js"
    ]
    assert js_expected == cache_exported.js
    assert fonts_exported_full == cache_exported.fonts


def test_export_no_confirm(
    existing_cache,
    path_archive,
    js_exported_full,
    fonts_exported_full
):
    assert path_archive.is_file()
    dmp_offline_cache("--export", str(path_archive), "--no-refresh", "--yes")

    cache_exported = Cache.from_path(path_archive, ConfirmYes())
    assert js_exported_full == cache_exported.js
    assert fonts_exported_full == cache_exported.fonts


def test_bail_stdin_closed(existing_cache, path_archive):
    assert 11 == dmp_offline_cache(
        "--import",
        str(path_archive),
        input="",
        is_returncode_checked=False
    )
