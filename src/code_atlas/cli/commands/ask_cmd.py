import typer

from code_atlas.cli.ui import print_pending


def run(
    question: str = typer.Argument(..., help="Question to ask about the indexed repo."),
) -> None:
    """Ask a one-shot question about an indexed repo.

    Answers are grounded in file:line evidence from the actual source —
    the same trust mechanism the verifier uses, not a guess.

    Not implemented yet — coming in a later build phase.
    """
    print_pending("ask is not implemented yet — coming in a later build phase.")
    raise typer.Exit(code=0)
