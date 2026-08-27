from pathlib import Path

from code_atlas.writers.claude_md import render
from code_atlas.writers.context import RepoContext


def write(ctx: RepoContext, repo_root: Path) -> Path:
    path = repo_root / "AGENTS.md"
    path.write_text(render(ctx, claude_specific=False))
    return path
