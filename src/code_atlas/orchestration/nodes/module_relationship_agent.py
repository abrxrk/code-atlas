import json
from pathlib import Path

from code_atlas.llm.agent_backend import AgentBackend
from code_atlas.orchestration.nodes.repo_mapper import RepoMapResult
from code_atlas.orchestration.state import ModuleEdge
from code_atlas.tools.fs_walk import FileEntry
from code_atlas.tools.parsers import ast_js_ts, ast_python

_MAX_FILES_PER_CLUSTER = 40
_JS_SUFFIXES = {".js", ".jsx", ".ts", ".tsx"}


def run(repo_map: RepoMapResult, backend: AgentBackend) -> list[ModuleEdge]:
    """Resolve internal (same-repo) import edges, cluster by cluster.

    Each cluster gets one prompt so no single LLM call sees the whole repo
    (see plan.md "Parallel fan-out"). External/unresolved imports are left
    out of the result entirely rather than guessed at.
    """
    edges: list[ModuleEdge] = []
    for cluster_name, entries in repo_map.clusters.items():
        parsed = _parse_cluster_files(repo_map.root, entries)
        if not parsed:
            continue

        prompt = _build_prompt(cluster_name, parsed)
        try:
            response = backend.run(prompt)
        except Exception as exc:  # backend/provider failures shouldn't crash the whole run
            print(f"warning: module_relationship_agent call failed for cluster '{cluster_name}': {exc}")
            continue

        edges.extend(_parse_response(cluster_name, response.text))

    return edges


def _parse_cluster_files(root: Path, entries: list[FileEntry]) -> dict[str, list[str]]:
    parsed: dict[str, list[str]] = {}
    for entry in entries[:_MAX_FILES_PER_CLUSTER]:
        suffix = entry.path.suffix
        if suffix == ".py":
            info = ast_python.parse(root / entry.path)
        elif suffix in _JS_SUFFIXES:
            info = ast_js_ts.parse(root / entry.path)
        else:
            continue
        if info is None:
            continue
        parsed[str(entry.path)] = info.imports
    return parsed


def _build_prompt(cluster_name: str, parsed: dict[str, list[str]]) -> str:
    file_list = "\n".join(f"- {path}" for path in parsed)
    imports_block = "\n".join(f"{path}: {imports}" for path, imports in parsed.items())
    return (
        f"You are analyzing the '{cluster_name}' cluster of a codebase for internal "
        "module dependencies.\n\n"
        f"Files in this cluster:\n{file_list}\n\n"
        "Each file's raw imports, exactly as written in source (not yet resolved to "
        f"actual files):\n{imports_block}\n\n"
        "For every import, decide whether it refers to another file inside this repo "
        "(internal) or to an external/third-party package. Resolve internal imports to "
        "the exact relative file path of the target file.\n\n"
        "Reply with ONLY a JSON array of objects, each with a \"source\" key (the relative "
        "path of the file doing the importing) and a \"target\" key (the resolved relative "
        "path of the internal import). Omit external or unresolved imports entirely — never "
        "invent a fake target. No explanation, no markdown, no code fences — just the raw "
        "JSON array."
    )


def _parse_response(cluster_name: str, text: str) -> list[ModuleEdge]:
    cleaned = _strip_code_fences(text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        print(f"warning: module_relationship_agent got unparseable JSON for cluster '{cluster_name}', skipping")
        return []

    if not isinstance(data, list):
        print(f"warning: module_relationship_agent response for cluster '{cluster_name}' was not a JSON array, skipping")
        return []

    edges: list[ModuleEdge] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        source = item.get("source")
        target = item.get("target")
        if isinstance(source, str) and isinstance(target, str):
            edges.append(ModuleEdge(source=source, target=target))
    return edges


def _strip_code_fences(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    lines = lines[1:]  # drop opening ``` or ```json
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()
