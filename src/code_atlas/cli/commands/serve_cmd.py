import typer

from code_atlas.cli.ui import print_pending


def run() -> None:
    """Run the local server in the foreground, for debugging.

    code-atlas normally runs indexing/Q&A through a detached background
    server; this runs it in the foreground instead so you can see its
    logs directly.

    Not implemented yet — coming in a later build phase.
    """
    print_pending("serve is not implemented yet — coming in a later build phase.")
    raise typer.Exit(code=0)
