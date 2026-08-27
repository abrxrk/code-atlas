"""Plain, framework-agnostic functions shared by the verifier and the Q&A agent.

No LangChain/MCP decorators here on purpose — llm/langchain_backend.py wraps
these with @tool for create_react_agent, and tools/mcp_server.py wraps the
same functions for the Claude Code CLI backend. Both call these directly so
"verify against source" and "answer against source" always use the same
trust mechanism, regardless of which backend produced the answer.
"""

from pathlib import Path

from code_atlas.tools.grep import grep as _grep

_MAX_READ_CHARS = 20_000


def read_file(repo_root: str, relative_path: str) -> str:
    try:
        path = _resolve(repo_root, relative_path)
    except ValueError as exc:
        return f"Error: {exc}"
    if not path.is_file():
        return f"Error: {relative_path} does not exist or is not a file."
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return f"Error reading {relative_path}: {exc}"
    if len(text) > _MAX_READ_CHARS:
        text = text[:_MAX_READ_CHARS] + "\n... (truncated)"
    return text


def grep_repo(repo_root: str, pattern: str) -> str:
    matches = _grep(Path(repo_root), pattern)
    if not matches:
        return f"No matches for pattern: {pattern}"
    return "\n".join(f"{m.path}:{m.line}: {m.text}" for m in matches)


def list_dir(repo_root: str, relative_path: str = "") -> str:
    try:
        path = _resolve(repo_root, relative_path)
    except ValueError as exc:
        return f"Error: {exc}"
    if not path.is_dir():
        return f"Error: {relative_path or '.'} is not a directory."
    entries = sorted(p.name + ("/" if p.is_dir() else "") for p in path.iterdir())
    return "\n".join(entries) if entries else "(empty)"


def list_modules(repo_root: str) -> str:
    modules_dir = Path(repo_root) / ".code-atlas" / "modules"
    if not modules_dir.is_dir():
        return "No module docs found — run `code-atlas index` first."
    names = sorted(p.stem for p in modules_dir.glob("*.md"))
    return "\n".join(names) if names else "(no modules)"


def get_module_doc(repo_root: str, module_name: str) -> str:
    path = Path(repo_root) / ".code-atlas" / "modules" / f"{module_name}.md"
    if not path.is_file():
        return f"Error: no module doc named '{module_name}'."
    return path.read_text(encoding="utf-8")


def _resolve(repo_root: str, relative_path: str) -> Path:
    root = Path(repo_root).resolve()
    target = (root / relative_path).resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"path {relative_path!r} escapes the repo root")
    return target
