from collections.abc import Sequence
import inspect as ins
import json
from pathlib import Path
import platformdirs
from typing import Any, Callable, cast, TypeVar, Union
from warnings import warn

try:
    from typing import ParamSpec
except ImportError:
    from typing_extensions import ParamSpec


P = ParamSpec("P")
T = TypeVar("T")


DEFAULT_CONFIG = {
    "dpi": 100,
    "figsize": (10, 10),
    "cdn_url": "unpkg.com",
}


class ConfigError(Exception):

    def __init__(self, message: str, parameter: ins.Parameter) -> None:
        super().__init__(message)
        self.parameter = parameter


UnconfigurableParameters = Sequence[str]


class ConfigManager:
    """Configuration manager for the datamapplot package."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._config = {}
        return cls._instance

    def __init__(self):
        if not self._config:
            self._config_dir = platformdirs.user_config_dir("datamapplot")
            self._config_file = Path(self._config_dir) / "config.json"
            self._config = DEFAULT_CONFIG.copy()

            self._ensure_config_file()
            self._load_config()

    def _ensure_config_file(self) -> None:
        """Create config directory and file if they don't exist."""
        try:
            self._config_file.parent.mkdir(parents=True, exist_ok=True)

            if not self._config_file.exists():
                with open(self._config_file, 'w') as f:
                    json.dump(DEFAULT_CONFIG, f, indent=2)
        except Exception as e:
            warn(f"Error creating config file: {e}")

    def _load_config(self) -> None:
        """Load configuration from file."""
        try:
            with open(self._config_file) as f:
                loaded_config = json.load(f)
                self._config.update(loaded_config)
        except Exception as e:
            warn(f"Error loading config file: {e}")

    def save(self) -> None:
        """Save current configuration to file."""
        try:
            with open(self._config_file, 'w') as f:
                json.dump(self._config, f, indent=2)
        except Exception as e:
            warn(f"Error saving config file: {e}")

    def __getitem__(self, key):
        return self._config[key]

    def __setitem__(self, key, value):
        self._config[key] = value

    def __delitem__(self, key):
        del self._config[key]

    def __contains__(self, key):
        return key in self._config

    def complete(
        self,
        fn_or_unc: Union[None, UnconfigurableParameters, Callable[P, T]] = None,
        unconfigurable: UnconfigurableParameters = set(),
    ) -> Union[Callable[[Callable[P, T]], Callable[P, T]], Callable[P, T]]:
        def decorator(fn: Callable[P, T]) -> Callable[P, T]:
            sig = ins.signature(fn)

            def fn_with_config(*args, **kwargs):
                bound_args = sig.bind(*args, **kwargs)
                bindings = bound_args.arguments
                from_config = {}
                for name, param in sig.parameters.items():
                    if name not in bindings and name in self:
                        if not _is_admissible(param):
                            raise ConfigError(
                                "Only keyword (or plausibly keyword) parameters "
                                "can be set through the DataMapPlot configuration "
                                f"file. Parameter {param.name} ({param.kind}) "
                                "is thus not admissible.",
                                param
                            )
                        if name in unconfigurable:
                            raise ConfigError(
                                f"Parameter {param.name} is deliberately listed as "
                                "forbidden from being defined through the DataMapPlot "
                                "configuration file.",
                                param
                            )
                        from_config[name] = self[name]
                return fn(*bound_args.args, **(bound_args.kwargs | from_config))

            fn_with_config._gets_completed = True
            # fn_with_config.__name__ = fn.__name__
            fn_with_config.__doc__ = fn.__doc__
            # fn_with_config.__dict__ = fn.__dict__
            fn_with_config.__module__ = fn.__module__
            fn_with_config.__annotations__ = fn.__annotations__
            fn_with_config.__defaults__ = fn.__defaults__
            fn_with_config.__kwdefaults__ = fn.__kwdefaults__
            return fn_with_config

        if fn_or_unc is None:
            return decorator
        elif not hasattr(fn_or_unc, "__call__"):
            unconfigurable = cast(UnconfigurableParameters, fn_or_unc)
            return decorator
        return decorator(fn_or_unc)

    @staticmethod
    def gets_completed(func) -> bool:
        return hasattr(func, "_gets_completed") and func._gets_completed


_KINDS_ADMISSIBLE = {ins.Parameter.POSITIONAL_OR_KEYWORD, ins.Parameter.KEYWORD_ONLY}


def _is_admissible(param: ins.Parameter) -> bool:
    return param.kind in _KINDS_ADMISSIBLE
