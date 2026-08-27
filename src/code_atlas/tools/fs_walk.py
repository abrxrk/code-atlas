from dataclasses import dataclass, field
from pathlib import Path

import pathspec

# Directories that are never useful to index, regardless of .gitignore content —
# either VCS/tool-internal or large enough to make walking pointless.
ALWAYS_IGNORE = {".git", ".code-atlas", "__pycache__", "node_modules", ".venv", "venv"}


@dataclass
class FileEntry:
    path: Path  # relative to repo root
    size: int
    cluster: str  # top-level directory name, or "" for root-level files


@dataclass
class RepoMap:
    root: Path
    files: list[FileEntry] = field(default_factory=list)

    @property
    def clusters(self) -> dict[str, list[FileEntry]]:
        grouped: dict[str, list[FileEntry]] = {}
        for entry in self.files:
            grouped.setdefault(entry.cluster, []).append(entry)
        return grouped


def walk(root: Path) -> RepoMap:
    """Walk `root`, respecting its top-level .gitignore, and build a file inventory.

    Only the repo-root .gitignore is consulted (not nested per-directory
    ones) — combined with ALWAYS_IGNORE this covers the common case
    without the complexity of cascading multiple gitignore files.
    """
    root = root.resolve()
    spec = _load_gitignore(root)
    entries: list[FileEntry] = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in ALWAYS_IGNORE for part in rel.parts):
            continue
        if spec.match_file(rel.as_posix()):
            continue
        cluster = rel.parts[0] if len(rel.parts) > 1 else ""
        entries.append(FileEntry(path=rel, size=path.stat().st_size, cluster=cluster))

    return RepoMap(root=root, files=entries)


def _load_gitignore(root: Path) -> pathspec.PathSpec:
    gitignore = root / ".gitignore"
    lines = gitignore.read_text().splitlines() if gitignore.exists() else []
    return pathspec.PathSpec.from_lines("gitwildmatch", lines)
