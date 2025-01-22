from copy import copy
import inspect as ins
from pathlib import Path
import platformdirs
import pytest

from .. import create_plot, create_interactive_plot, render_plot, render_html
from ..config import ConfigManager, ConfigError
from ..selection_handlers import DisplaySample, WordCloud, CohereSummary


@pytest.fixture
def no_change_to_config_file():
    cfgmgr = ConfigManager()
    assert cfgmgr._config_file.is_file()
    contents_before = cfgmgr._config_file.read_bytes()
    try:
        yield None
    finally:
        contents_after = cfgmgr._config_file.read_bytes()
        if contents_after != contents_before:
            cfgmgr._config_file.write_bytes(contents_before)
            pytest.fail(
                "Unit test was supposed not to change the configuration file, "
                "yet it did."
            )


def test_tweak_config_sanity(no_change_to_config_file):
    cfgmgr = ConfigManager()
    cfgmgr["asdf"] = "qwer"


@pytest.fixture
def config(no_change_to_config_file):
    config = ConfigManager()
    orig = copy(config._config)
    if "font_family" in config._config:
        del config._config["font_family"]
    yield config
    config._config = orig


@pytest.fixture
def the_func(config):
    for name in ["a", "args", "b", "c", "dont_touch", "kwargs"]:
        assert name not in config

    @config.complete({"dont_touch"})
    def _the_func(a, *args, b=None, c="asdf", dont_touch="nope", **kwargs):
        return a, args, b, c, dont_touch, kwargs
    return _the_func


def test_no_config_args(the_func, config):
    config["args"] = ("heck", "no")
    with pytest.raises(ConfigError):
        the_func("A")


def test_no_config_kwargs(the_func, config):
    config["kwargs"] = {"heck": "no"}
    with pytest.raises(ConfigError):
        the_func("A")


def test_config_positional_useless(the_func, config):
    config["a"] = "how would that even work?"  # Can never reach.
    assert the_func("A") == ("A", (), None, "asdf", "nope", {})


def test_fetch_b_config(the_func, config):
    config["b"] = 98
    assert the_func("A") == ("A", (), 98, "asdf", "nope", {})


def test_override_configed_b(the_func, config):
    config["b"] = 98
    assert the_func("A", "B", b=3) == ("A", ("B",), 3, "asdf", "nope", {})


def test_nonconfiged_c(the_func, config):
    config["b"] = 98
    assert the_func("A", c="qwer") == ("A", (), 98, "qwer", "nope", {})


def test_no_config_donttouch(the_func, config):
    config["dont_touch"] = "this mustn't work"
    with pytest.raises(ConfigError):
        the_func("A")


def test_override_donttouch(the_func):
    assert the_func("A", dont_touch="poke") == ("A", (), None, "asdf", "poke", {})


@pytest.mark.parametrize(
    "func",
    [
        create_plot,
        create_interactive_plot,
        render_plot,
        render_html,
        DisplaySample.__init__,
        WordCloud.__init__,
        CohereSummary.__init__
    ]
)
def test_has_config(func):
    assert ConfigManager.gets_completed(func)


def test_sanity_config_display_sample(config):
    assert DisplaySample().font_family is None
    config["font_family"] = "Roboto"
    assert DisplaySample().font_family == "Roboto"
