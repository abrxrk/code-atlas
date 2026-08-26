from pathlib import Path

CONFIG_DIR = Path.home() / ".code-atlas"
CONFIG_FILE = CONFIG_DIR / "config.toml"
LOG_DIR = CONFIG_DIR / "logs"


def ensure_config_dir() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


def ensure_log_dir() -> Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    return LOG_DIR
