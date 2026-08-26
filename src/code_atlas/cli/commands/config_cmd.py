import typer
from rich import box
from rich.table import Table

from code_atlas.cli.ui import ACCENT, MUTED, PENDING, console
from code_atlas.config.paths import CONFIG_FILE
from code_atlas.config.settings import ROLES, config_exists, load_settings

app = typer.Typer(
    help=(
        "View or edit LLM provider configuration (~/.code-atlas/config.toml).\n\n"
        "Runs `show` if called with no subcommand."
    ),
    no_args_is_help=False,
)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        show()


@app.command("show")
def show() -> None:
    """Print the resolved configuration (secrets redacted).

    Shows which provider/model is set for each role (analysis, verifier,
    qa) and a redacted tail of each API key, so you can confirm what's
    configured without exposing secrets.
    """
    if not config_exists():
        console.print(f"[{PENDING}]No config file yet at {CONFIG_FILE}.[/{PENDING}]")
        console.print(f"[{MUTED}]Interactive setup runs the first time you use `code-atlas index`.[/{MUTED}]")
        return

    settings = load_settings()
    table = Table(
        title="code-atlas config",
        title_style=f"bold {ACCENT}",
        title_justify="left",
        header_style=f"bold {ACCENT}",
        box=box.SIMPLE,
    )
    table.add_column("Role")
    table.add_column("Provider")
    table.add_column("Model")
    table.add_column("API key")

    for role_name in ROLES:
        role = getattr(settings, role_name)
        if role is None:
            table.add_row(role_name, f"[{MUTED}]not set[/{MUTED}]", "-", "-")
            continue
        redacted = f"{'*' * 8}{role.api_key[-4:]}" if role.api_key else f"[{MUTED}]-[/{MUTED}]"
        table.add_row(role_name, role.provider, role.model, redacted)

    console.print(table)


@app.command("path")
def path() -> None:
    """Print the path to the config file (~/.code-atlas/config.toml)."""
    console.print(str(CONFIG_FILE))
