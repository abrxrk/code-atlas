from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from code_atlas.orchestration.state import EntryPoint, IndexState, ModuleEdge

_OUTPUT_DIRNAME = ".code-atlas"
_MODULES_DIRNAME = "modules"


@dataclass
class ModuleDocsResult:
    index_path: Path
    module_paths: list[Path]
    dependency_graph_path: Path
    entry_points_path: Path


def write(state: IndexState, repo_root: Path) -> ModuleDocsResult:
    """Write the .code-atlas/ deep-dive output: per-cluster module docs,
    a table-of-contents index.md, dependency-graph.json, and entry-points.md.
    """
    output_dir = repo_root / _OUTPUT_DIRNAME
    modules_dir = output_dir / _MODULES_DIRNAME
    modules_dir.mkdir(parents=True, exist_ok=True)

    clusters = state.repo_map.clusters if state.repo_map else {}

    module_paths: list[Path] = []
    index_rows: list[tuple[str, str, int]] = []

    for cluster_name in sorted(clusters):
        files = clusters[cluster_name]
        slug = _slug(cluster_name)
        entry_points = [ep for ep in state.entry_points if _cluster_of(ep.file) == cluster_name]
        edges = [
            edge
            for edge in state.module_edges
            if _cluster_of(edge.source) == cluster_name or _cluster_of(edge.target) == cluster_name
        ]

        doc_path = modules_dir / f"{slug}.md"
        doc_path.write_text(_render_module_doc(cluster_name, files, entry_points, edges))
        module_paths.append(doc_path)
        index_rows.append((cluster_name, slug, len(files)))

    index_path = output_dir / "index.md"
    index_path.write_text(_render_index(index_rows))

    dependency_graph_path = output_dir / "dependency-graph.json"
    dependency_graph_path.write_text(json.dumps([edge.model_dump() for edge in state.module_edges], indent=2))

    entry_points_path = output_dir / "entry-points.md"
    entry_points_path.write_text(_render_entry_points(state.entry_points))

    return ModuleDocsResult(
        index_path=index_path,
        module_paths=module_paths,
        dependency_graph_path=dependency_graph_path,
        entry_points_path=entry_points_path,
    )


def format_entry_point(entry_point: EntryPoint) -> str:
    line_part = f":{entry_point.line}" if entry_point.line is not None else ""
    return f"`{entry_point.file}{line_part}` -- {entry_point.description}"


def _cluster_of(file_path: str) -> str:
    """Same top-level-directory rule fs_walk.walk uses to assign clusters."""
    parts = Path(file_path).parts
    return parts[0] if len(parts) > 1 else ""


def _slug(cluster_name: str) -> str:
    return cluster_name.replace("/", "-") if cluster_name else "root"


def _render_module_doc(
    cluster_name: str,
    files: list,
    entry_points: list[EntryPoint],
    edges: list[ModuleEdge],
) -> str:
    title = cluster_name if cluster_name else "(root)"
    lines = [f"# Module: {title}", "", "## Files", ""]
    for entry in sorted(files, key=lambda f: f.path.as_posix()):
        lines.append(f"- `{entry.path.as_posix()}` ({entry.size} bytes)")

    lines += ["", "## Entry points", ""]
    if entry_points:
        for ep in entry_points:
            lines.append(f"- {format_entry_point(ep)}")
    else:
        lines.append("_None detected._")

    lines += ["", "## Dependency edges", ""]
    if edges:
        for edge in edges:
            lines.append(f"- `{edge.source}` -> `{edge.target}`")
    else:
        lines.append("_None detected._")

    lines.append("")
    return "\n".join(lines)


def _render_index(rows: list[tuple[str, str, int]]) -> str:
    lines = ["# Module index", "", "| Cluster | Files | Doc |", "| --- | --- | --- |"]
    for cluster_name, slug, file_count in rows:
        title = cluster_name if cluster_name else "(root)"
        lines.append(f"| {title} | {file_count} | [{slug}.md]({_MODULES_DIRNAME}/{slug}.md) |")
    lines.append("")
    return "\n".join(lines)


def _render_entry_points(entry_points: list[EntryPoint]) -> str:
    lines = ["# Entry points", ""]
    if not entry_points:
        lines.append("_None detected._")
    for ep in entry_points:
        lines.append(f"- {format_entry_point(ep)}")
    lines.append("")
    return "\n".join(lines)
