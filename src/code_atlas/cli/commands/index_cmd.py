from pathlib import Path

import typer

from code_atlas.cli.ui import print_pending


def run(
    path: Path = typer.Argument(Path("."), help="Repository to index (defaults to the current directory)."),
) -> None:
    """Index a repository into verified, agent-readable docs.

    Walks the repo, detects its tech stack, maps entry points and module
    relationships, verifies every claim against the actual source, and
    writes CLAUDE.md/AGENTS.md plus a deeper .code-atlas/ doc set.

    Not implemented yet — coming in a later build phase.
    """
    print_pending(f"index [dim]({path})[/dim] is not implemented yet — coming in a later build phase.")
    raise typer.Exit(code=0)
