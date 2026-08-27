from dataclasses import dataclass
from pathlib import Path

from code_atlas.tools import fs_walk
from code_atlas.tools.parsers.manifest_parsers import ManifestInfo, find_manifests


@dataclass
class RepoMapResult:
    root: Path
    file_count: int
    clusters: dict[str, list[fs_walk.FileEntry]]
    manifests: list[ManifestInfo]


def run(root: Path) -> RepoMapResult:
    repo_map = fs_walk.walk(root)
    manifests = find_manifests(repo_map.root)
    return RepoMapResult(
        root=repo_map.root,
        file_count=len(repo_map.files),
        clusters=repo_map.clusters,
        manifests=manifests,
    )
