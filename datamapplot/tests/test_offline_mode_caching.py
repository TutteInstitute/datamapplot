from pathlib import Path
import pytest
from unittest.mock import patch

from ..offline_mode_caching import (
    Cache,
    ConfirmInteractiveStdio,
    ConfirmYes,
    DEFAULT_CACHE_FILES,
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
    try:
        cache_in_mem = {
            key: Path(path).read_bytes()
            for key, path in DEFAULT_CACHE_FILES.items()
            if Path(path).is_file()
        }
        yield
    finally:
        for key, path in DEFAULT_CACHE_FILES.items():
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_bytes(cache_in_mem[key])


@pytest.fixture
def no_cache(preserving_cache):
    for path in DEFAULT_CACHE_FILES.values():
        Path(path).unlink(missing_ok=True)
    Path(DEFAULT_CACHE_FILES["javascript"]).parent.rmdir()


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
def existing_cache(preserving_cache, js_old, fonts_old):
    for key, content in [("javascript", js_old), ("fonts", fonts_old)]:
        Path(DEFAULT_CACHE_FILES[key]).write_text(json.dumps(content), encoding="utf-8")


@pytest.fixture
def dir_cache(tmp_path):
    dir = tmp_path / "cache"
    dir.mkdir(parents=True, exist_ok=True)
    return dir


@pytest.fixture
def zip_cache(tmp_path):
    return tmp_path / "cache.zip"


@pytest.mark.parametrize(
    "type_store,validate_store",
    [("dir", Path.is_dir), ("zip", Path.is_file)]
)
def test_store(type_store, validate_store, dir_cache, zip_cache, js_old, fonts_old):
    path_cache = {"dir": dir_cache, "zip": zip_cache}[type_store]
    cache = Cache(
        js=js_old,
        fonts=fonts_old,
        confirm=ConfirmYes(),
        store=make_store(path_cache)
    )
    cache.save()
    assert validate_store(path_cache)
    assert cache == Cache.from_path(path_cache, ConfirmYes())


@pytest.mark.skip
def test_import_no_clobber():
    raise NotImplementedError()


@pytest.mark.skip
def test_import_clobber_partial():
    raise NotImplementedError()


@pytest.mark.skip
def test_import_no_confirm():
    raise NotImplementedError()


@pytest.mark.skip
def test_export_no_clobber():
    raise NotImplementedError()


@pytest.mark.skip
def test_export_clobber_partial():
    raise NotImplementedError()


@pytest.mark.skip
def test_export_no_confirm():
    raise NotImplementedError()
