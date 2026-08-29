import json
from pathlib import Path

import httpx
import typer
from httpx_sse import connect_sse
from rich.live import Live
from rich.table import Table

from code_atlas.cli.ui import ACCENT, MUTED, SUCCESS, console, print_error, print_success
from code_atlas.config.settings import config_exists
from code_atlas.config.wizard import run_setup_wizard
from code_atlas.server.process import ensure_server_running

_INDEX_TIMEOUT_S = 300.0

_STAGE_LABELS = {
    "repo_mapper": "Mapping repo",
    "tech_stack_detector": "Detecting tech stack",
    "entry_point_agent": "Finding entry points",
    "module_relationship_agent": "Mapping module relationships",
    "verifier": "Verifying claims",
    "entry_point_recheck": "Re-checking entry points",
    "module_relationship_recheck": "Re-checking module edges",
    "writer": "Writing docs",
}
_RETRY_STAGES = {"verifier", "entry_point_recheck", "module_relationship_recheck"}


def run(
    path: Path = typer.Argument(Path("."), help="Repository to index (defaults to the current directory)."),
) -> None:
    """Index a repository into verified, agent-readable docs.

    Runs the full LangGraph pipeline: repo mapping, tech-stack detection,
    entry-point + module-relationship analysis (in parallel), verification
    with a targeted retry loop, then writes CLAUDE.md/AGENTS.md plus the
    deeper .code-atlas/ output. The pipeline itself runs inside the local
    FastAPI server, not in this process — this command streams its
    progress and prints a summary when it's done.
    """
    if not config_exists():
        run_setup_wizard()

    root = path.resolve()
    if not root.is_dir():
        print_error(f"{root} is not a directory.")
        raise typer.Exit(code=1)

    port = ensure_server_running()
    summary, error_message = _run_with_progress(port, root)

    if error_message:
        print_error(f"Indexing failed: {error_message}")
        raise typer.Exit(code=1)

    console.print()
    print_success(f"Indexed {summary['file_count']} files. Wrote {len(summary['output_paths'])} output file(s).")
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


def _run_with_progress(port: int, root: Path) -> tuple[dict | None, str | None]:
    completed: list[str] = []
    current: str | None = None
    retry_note = ""
    summary: dict | None = None
    error_message: str | None = None

    def render() -> Table:
        table = Table(show_header=False, box=None, padding=(0, 1))
        for stage, label in _STAGE_LABELS.items():
            if stage == current:
                mark = f"[{ACCENT}]○[/{ACCENT}]"
                text = f"{label} {retry_note}".strip()
            elif stage in completed:
                mark = f"[{SUCCESS}]✓[/{SUCCESS}]"
                text = label
            else:
                mark = f"[{MUTED}]·[/{MUTED}]"
                text = f"[{MUTED}]{label}[/{MUTED}]"
            table.add_row(mark, text)
        return table

    try:
        with httpx.Client(timeout=_INDEX_TIMEOUT_S) as client, connect_sse(
            client, "POST", f"http://127.0.0.1:{port}/index", json={"repo_root": str(root)}
        ) as event_source, Live(render(), console=console, refresh_per_second=8, transient=True) as live:
            for sse in event_source.iter_sse():
                payload = json.loads(sse.data)
                stage = payload["stage"]

                if stage == "complete":
                    if current and current not in completed:
                        completed.append(current)
                    current = None
                    live.update(render())
                    summary = payload["result"]["summary"]
                    break
                if stage == "error":
                    error_message = payload["message"]
                    break

                if current and current != stage and current not in completed:
                    completed.append(current)
                current = stage
                retry_count = payload.get("retry_count", 0)
                retry_note = f"(retry {retry_count})" if stage in _RETRY_STAGES and retry_count else ""
                live.update(render())
    except httpx.HTTPStatusError as exc:
        return None, f"the server returned {exc.response.status_code}. See server logs for details."
    except httpx.HTTPError as exc:
        return None, f"could not reach the local server ({exc})."

    return summary, error_message
