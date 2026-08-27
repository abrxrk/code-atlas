import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from code_atlas.config.paths import CONFIG_DIR, CONFIG_FILE
from code_atlas.config.settings import ROLES, config_exists, load_settings

MIN_PYTHON = (3, 11)


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str


def run_checks() -> list[CheckResult]:
    checks = [
        _check_python_version(),
        _check_config_exists(),
        _check_config_dir_writable(),
    ]
    claude_check = _check_claude_code_cli()
    if claude_check is not None:
        checks.append(claude_check)
    return checks


def _check_python_version() -> CheckResult:
    version = sys.version.split()[0]
    ok = sys.version_info[:2] >= MIN_PYTHON
    min_str = ".".join(map(str, MIN_PYTHON))
    detail = version if ok else f"{version} (need >= {min_str})"
    return CheckResult(name="Python version", passed=ok, detail=detail)


def _check_config_exists() -> CheckResult:
    exists = config_exists()
    detail = str(CONFIG_FILE) if exists else f"not found — run `code-atlas config` (expected at {CONFIG_FILE})"
    return CheckResult(name="Config file", passed=exists, detail=detail)


def _check_config_dir_writable() -> CheckResult:
    return CheckResult(
        name="Config directory writable",
        passed=_is_writable(CONFIG_DIR),
        detail=str(CONFIG_DIR),
    )


def _check_claude_code_cli() -> CheckResult | None:
    if not config_exists():
        return None
    settings = load_settings()
    uses_claude_code = any(getattr(settings, role) is not None and getattr(settings, role).provider == "claude-code" for role in ROLES)
    if not uses_claude_code:
        return None
    found = shutil.which("claude") is not None
    detail = "found on PATH" if found else "not found on PATH — install Claude Code and log in, or switch that role's provider"
    return CheckResult(name="Claude Code CLI", passed=found, detail=detail)


def _is_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-test"
        probe.touch()
        probe.unlink()
        return True
    except OSError:
        return False
