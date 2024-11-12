from warnings import warn
import json
import platformdirs
from pathlib import Path

DEFAULT_CONFIG = {
    "dpi": 100,
    "figsize": (10, 10),
    "cdn_url": "unpkg.com",
}

class ConfigManager:
    """Configuration manager for the datamapplot package."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._config = {}
        return cls._instance
    
    def __init__(self):
        if self._instance is None:
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

    