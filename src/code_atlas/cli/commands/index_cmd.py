from pathlib import Path

import httpx
import typer

from code_atlas.cli.ui import ACCENT, MUTED, console, print_error, print_success
from code_atlas.config.settings import config_exists
from code_atlas.config.wizard import run_setup_wizard
from code_atlas.server.process import ensure_server_running

_INDEX_TIMEOUT_S = 300.0


def run(
    path: Path = typer.Argument(Path("."), help="Repository to index (defaults to the current directory)."),
) -> None:
    """Index a repository into verified, agent-readable docs.

    Runs the full LangGraph pipeline: repo mapping, tech-stack detection,
    entry-point + module-relationship analysis (in parallel), then writes
    CLAUDE.md/AGENTS.md plus the deeper .code-atlas/ output. Verification
    lands in a later build phase. The pipeline itself runs inside the local
    FastAPI server, not in this process — this command just talks to it.
    """
    if not config_exists():
        run_setup_wizard()

    root = path.resolve()
    if not root.is_dir():
        print_error(f"{root} is not a directory.")
        raise typer.Exit(code=1)

    port = ensure_server_running()
    try:
        response = httpx.post(
            f"http://127.0.0.1:{port}/index",
            json={"repo_root": str(root)},
            timeout=_INDEX_TIMEOUT_S,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        print_error(f"Indexing failed: the server returned {exc.response.status_code}. See server logs for details.")
        raise typer.Exit(code=1) from None
    except httpx.HTTPError as exc:
        print_error(f"Indexing failed: could not reach the local server ({exc}).")
        raise typer.Exit(code=1) from None
    summary = response.json()["summary"]

    console.print()
    print_success(
        f"Indexed {summary['file_count']} files. Wrote {len(summary['output_paths'])} output file(s)."
    )
    if summary["languages"]:
        console.print(f"  [{ACCENT}]Languages:[/{ACCENT}] {', '.join(summary['languages'])}")
    if summary["frameworks"]:
        console.print(f"  [{ACCENT}]Frameworks:[/{ACCENT}] {', '.join(summary['frameworks'])}")
    console.print(f"  [{ACCENT}]Entry points found:[/{ACCENT}] {summary['entry_point_count']}")
    console.print(f"  [{ACCENT}]Module edges found:[/{ACCENT}] {summary['module_edge_count']}")
    console.print(
        f"  [{MUTED}]Wrote CLAUDE.md, AGENTS.md, and .code-atlas/"
        f"(index.md, modules/, dependency-graph.json, entry-points.md).[/{MUTED}]"
    )
    console.print()
