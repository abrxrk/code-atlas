import typer
from rich.table import Table

from code_atlas.cli.ui import ACCENT, ERROR, SUCCESS, console
from code_atlas.infra.doctor import run_checks


def run() -> None:
    """Check that code-atlas is set up correctly.

    Verifies your Python version, that a provider config exists, and
    that code-atlas can write to its local state directory
    (~/.code-atlas). Exits non-zero if any check fails.
    """
    checks = run_checks()

    table = Table(
        title="code-atlas doctor",
        title_style=f"bold {ACCENT}",
        title_justify="left",
        show_header=False,
        box=None,
        padding=(0, 1),
    )
    for check in checks:
        mark = f"[{SUCCESS}]✓[/{SUCCESS}]" if check.passed else f"[{ERROR}]✗[/{ERROR}]"
        table.add_row(mark, f"[bold]{check.name}[/bold]", f"[dim]{check.detail}[/dim]")

    console.print()
    console.print(table)
    console.print()

    if all(check.passed for check in checks):
        console.print(f"[{SUCCESS}]All checks passed.[/{SUCCESS}]")
    else:
        console.print(f"[{ERROR}]Some checks failed — see above.[/{ERROR}]")
        raise typer.Exit(code=1)
