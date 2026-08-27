from pathlib import Path

import httpx
import typer
from rich.markup import escape

from code_atlas.cli.ui import ACCENT, console, print_error, print_success
from code_atlas.config.settings import config_exists
from code_atlas.config.wizard import run_setup_wizard
from code_atlas.server.process import ensure_server_running

_ASK_TIMEOUT_S = 300.0


def run(
    question: str = typer.Argument(..., help="Question to ask about the repo in the current directory."),
) -> None:
    """Ask a one-shot question about the repo in the current directory.

    Answers are grounded in file:line evidence from the actual source, found
    live via tool-calling — the same trust mechanism the verifier uses, not
    a guess. Works best after `code-atlas index`, but still explores raw
    source directly if the repo hasn't been indexed yet.
    """
    if not config_exists():
        run_setup_wizard()

    root = Path.cwd()

    port = ensure_server_running()
    try:
        response = httpx.post(
            f"http://127.0.0.1:{port}/ask",
            json={"repo_root": str(root), "question": question},
            timeout=_ASK_TIMEOUT_S,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        print_error(f"Ask failed: the server returned {exc.response.status_code}. See server logs for details.")
        raise typer.Exit(code=1) from None
    except httpx.HTTPError as exc:
        print_error(f"Ask failed: could not reach the local server ({exc}).")
        raise typer.Exit(code=1) from None
    answer = response.json()["answer"]

    console.print()
    print_success("Answer:")
    console.print(f"[{ACCENT}]{escape(answer)}[/{ACCENT}]")
    console.print()
