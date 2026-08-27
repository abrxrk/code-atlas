from datetime import UTC, datetime
from pathlib import Path

import typer

from code_atlas.cli.ui import ACCENT, MUTED, console, print_error, print_success
from code_atlas.orchestration.nodes import repo_mapper, tech_stack_detector
from code_atlas.store.models import SessionState
from code_atlas.store.session_store import save_session
from code_atlas.writers.agents_md import write as write_agents_md
from code_atlas.writers.claude_md import write as write_claude_md
from code_atlas.writers.context import DirectoryEntry, RepoContext, TechStackSummary


def run(
    path: Path = typer.Argument(Path("."), help="Repository to index (defaults to the current directory)."),
) -> None:
    """Index a repository into verified, agent-readable docs.

    Currently covers repo mapping + tech-stack detection only (Phase 2):
    walks the repo, detects languages/frameworks/build tools, and writes
    CLAUDE.md/AGENTS.md from that. Entry points, module relationships,
    and verification land in later build phases.
    """
    root = path.resolve()
    if not root.is_dir():
        print_error(f"{root} is not a directory.")
        raise typer.Exit(code=1)

    repo_map = repo_mapper.run(root)
    stack = tech_stack_detector.run(repo_map)

    ctx = RepoContext(
        repo_name=_repo_name(repo_map, root),
        file_count=repo_map.file_count,
        tech_stack=TechStackSummary(
            languages=stack.languages,
            frameworks=stack.frameworks,
            build_tools=stack.build_tools,
            run_commands=stack.run_commands,
            notes=stack.notes,
        ),
        directories=sorted(
            (DirectoryEntry(name=name, file_count=len(files)) for name, files in repo_map.clusters.items()),
            key=lambda entry: entry.name,
        ),
    )

    claude_path = write_claude_md(ctx, root)
    agents_path = write_agents_md(ctx, root)
    save_session(
        root,
        SessionState(
            repo_root=str(root),
            indexed_at=datetime.now(UTC).isoformat(),
            file_count=repo_map.file_count,
            languages=stack.languages,
            frameworks=stack.frameworks,
        ),
    )

    console.print()
    print_success(f"Indexed {repo_map.file_count} files across {len(repo_map.clusters)} top-level directories.")
    if stack.languages:
        console.print(f"  [{ACCENT}]Languages:[/{ACCENT}] {', '.join(stack.languages)}")
    if stack.frameworks:
        console.print(f"  [{ACCENT}]Frameworks:[/{ACCENT}] {', '.join(stack.frameworks)}")
    if stack.notes:
        console.print(f"  [{MUTED}]{stack.notes}[/{MUTED}]")
    console.print(f"  [{MUTED}]Wrote {claude_path.name} and {agents_path.name}.[/{MUTED}]")
    console.print()
    console.print(
        f"[{MUTED}]This is Phase 2 output — tech stack + directory map only. "
        f"Entry points, module relationships, and verification land in later phases.[/{MUTED}]"
    )


def _repo_name(repo_map: repo_mapper.RepoMapResult, root: Path) -> str:
    for manifest in repo_map.manifests:
        if manifest.name:
            return manifest.name
    return root.name
