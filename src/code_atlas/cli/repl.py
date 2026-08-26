import shlex

from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style

from code_atlas.cli.ui import ACCENT, console, print_banner

KNOWN_COMMANDS = ("index", "ask", "doctor", "config", "serve")

_STYLE = Style.from_dict(
    {
        "prompt": f"bold {ACCENT}",
        "placeholder": "fg:#6c6c6c italic",
        # prompt_toolkit's built-in default style hard-codes "bottom-toolbar" to
        # reverse video; without "noreverse" our fg/bg below get swapped into a
        # solid highlighted bar instead of plain dim text.
        "bottom-toolbar": "fg:#6c6c6c bg:default noreverse",
    }
)


def run_repl() -> None:
    from code_atlas.cli.app import app  # deferred: app.py imports this module at load time

    print_banner()
    console.rule(style="dim")

    session: PromptSession[str] = PromptSession(
        message=[("class:prompt", "› ")],
        placeholder=[("class:placeholder", 'Try "doctor" or ask a question…')],
        bottom_toolbar=[
            ("class:bottom-toolbar", "Ctrl+C to exit  ·  index · ask · doctor · config · serve · help")
        ],
        style=_STYLE,
    )

    while True:
        try:
            line = session.prompt().strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye.[/dim]")
            return

        if not line:
            continue
        if line in ("exit", "quit"):
            console.print("[dim]Goodbye.[/dim]")
            return

        args = _to_args(line)
        console.print()
        try:
            app(args=args, standalone_mode=False, prog_name="code-atlas")
        except Exception as exc:  # keep the REPL alive if a command misbehaves
            console.print(f"[red]Error: {exc}[/red]")
        console.print()


def _to_args(line: str) -> list[str]:
    if line in ("help", "--help", "-h"):
        return ["--help"]
    try:
        tokens = shlex.split(line)
    except ValueError:
        return ["ask", line]
    if tokens and tokens[0] in KNOWN_COMMANDS:
        return tokens
    return ["ask", line]
