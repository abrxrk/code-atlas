import typer

from code_atlas.cli.commands import ask_cmd, config_cmd, doctor_cmd, index_cmd, mcp_serve_cmd, serve_cmd
from code_atlas.cli.ui import apply_help_theme

apply_help_theme()

app = typer.Typer(
    name="code-atlas",
    help="Index a codebase into verified, agent-readable docs — then ask it questions.",
    epilog="Run with no command to start an interactive session.",
    add_completion=False,
    no_args_is_help=False,
    rich_markup_mode="rich",
)

app.command("index")(index_cmd.run)
app.command("ask")(ask_cmd.run)
app.command("serve")(serve_cmd.run)
app.command("doctor")(doctor_cmd.run)
app.command("mcp-serve")(mcp_serve_cmd.run)
app.add_typer(config_cmd.app, name="config")


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is None:
        from code_atlas.cli.repl import run_repl

        run_repl()


def main() -> None:
    app()


if __name__ == "__main__":
    main()
