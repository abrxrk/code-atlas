from pathlib import Path

from rich.console import Console
from rich.text import Text

from code_atlas import __version__

ACCENT = "#D97757"
SUCCESS = "bold green"
ERROR = "bold red"
PENDING = "yellow"
MUTED = "dim"

console = Console()


def apply_help_theme() -> None:
    """Retint Typer's Rich-powered --help output to match ACCENT.

    Typer exposes its help styling as module-level constants on
    typer.rich_utils rather than a config option — this is the documented
    way to retheme it. Call once, before the app runs.
    """
    import typer.rich_utils as rich_utils

    rich_utils.STYLE_USAGE = f"bold {ACCENT}"
    rich_utils.STYLE_OPTION = f"bold {ACCENT}"
    rich_utils.STYLE_COMMANDS_TABLE_FIRST_COLUMN = f"bold {ACCENT}"


def _short_cwd() -> str:
    cwd = Path.cwd()
    try:
        return f"~/{cwd.relative_to(Path.home())}" if cwd != Path.home() else "~"
    except ValueError:
        return str(cwd)


def print_banner() -> None:
    console.print(
        Text.assemble(
            ("✳ ", f"bold {ACCENT}"),
            ("code-atlas", f"bold {ACCENT}"),
            (f"  v{__version__}", "dim"),
        )
    )
    console.print(Text(f"  verified codebase mapping · {_short_cwd()}", style="dim"))


def print_success(message: str) -> None:
    console.print(f"[{SUCCESS}]✓[/{SUCCESS}] {message}")


def print_error(message: str) -> None:
    console.print(f"[{ERROR}]✗[/{ERROR}] {message}")


def print_info(message: str) -> None:
    console.print(f"[{ACCENT}]›[/{ACCENT}] {message}")


def print_pending(message: str) -> None:
    console.print(f"[{PENDING}]○[/{PENDING}] {message}")
