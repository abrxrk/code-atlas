import json
import re

from code_atlas.llm.agent_backend import AgentBackend
from code_atlas.orchestration.nodes.repo_mapper import RepoMapResult
from code_atlas.orchestration.state import EntryPoint
from code_atlas.tools.parsers import ast_js_ts, ast_python

_MAX_FILES_PER_CLUSTER = 40
_JS_TS_SUFFIXES = {".js", ".jsx", ".ts", ".tsx"}
_CODE_FENCE_RE = re.compile(r"^```[a-zA-Z]*\n|\n```$")


def run(repo_map: RepoMapResult, backend: AgentBackend) -> list[EntryPoint]:
    entry_points: list[EntryPoint] = []

    for cluster_name, files in repo_map.clusters.items():
        if not files:
            continue

        relevant = [f for f in files if f.path.suffix in ({".py"} | _JS_TS_SUFFIXES)][:_MAX_FILES_PER_CLUSTER]
        if not relevant:
            continue

        file_summaries = _summarize_files(repo_map.root, relevant)
        if not file_summaries:
            continue

        prompt = _build_prompt(cluster_name or "(root)", file_summaries)
        try:
            response = backend.run(prompt, tools=None)
        except Exception as exc:  # backend/provider failures shouldn't crash the whole run
            print(f"[entry_point_agent] warning: backend call failed for cluster '{cluster_name}', skipping: {exc}")
            continue

        parsed = _parse_entry_points(response.text)
        if parsed is None:
            print(f"[entry_point_agent] warning: could not parse entry points for cluster '{cluster_name}', skipping")
            continue

        entry_points.extend(parsed)

    return entry_points


def _summarize_files(root, files) -> list[tuple[str, list[str], int | None]]:
    summaries: list[tuple[str, list[str], int | None]] = []
    for entry in files:
        abs_path = root / entry.path
        suffix = entry.path.suffix

        if suffix == ".py":
            info = ast_python.parse(abs_path)
            names = info.defs if info else []
            main_guard_line = info.main_guard_line if info else None
        else:
            info = ast_js_ts.parse(abs_path)
            names = info.exports if info else []
            main_guard_line = None

        summaries.append((entry.path.as_posix(), names, main_guard_line))
    return summaries


def _build_prompt(cluster_name: str, file_summaries: list[tuple[str, list[str], int | None]]) -> str:
    lines = [f"Cluster: {cluster_name}"]
    for path, names, main_guard_line in file_summaries:
        names_str = ", ".join(names) if names else "(none found)"
        if main_guard_line is not None:
            names_str += f" [has `if __name__ == \"__main__\":` at line {main_guard_line}]"
        lines.append(f"- {path}: {names_str}")
    file_listing = "\n".join(lines)

    return (
        "You are analyzing a code cluster to find likely entry points — main functions, "
        "CLI commands, HTTP routes, or `if __name__ == \"__main__\"` blocks.\n\n"
        "Any file tagged `[has ... __main__ ...]` below is a CONFIRMED entry point — "
        "always include it. Only use function/class names to find additional entry points "
        "(e.g. a `main`/`cli` function, or a route decorator) beyond the confirmed ones.\n\n"
        f"{file_listing}\n\n"
        "Reply with ONLY a JSON array of objects, each having exactly these keys:\n"
        '  "description": short string describing the entry point\n'
        '  "file": the relative file path as a string\n'
        '  "line": integer line number, or null if unknown\n\n'
        "If there are no likely entry points in this cluster, reply with an empty JSON array []."
    )


def _parse_entry_points(text: str) -> list[EntryPoint] | None:
    cleaned = _CODE_FENCE_RE.sub("", text.strip()).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, list):
        return None

    try:
        return [EntryPoint(**item) for item in data]
    except (TypeError, ValueError):
        return None
