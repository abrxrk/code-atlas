import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

# .code-atlas is deliberately NOT in this set: it holds code-atlas's own
# generated docs (module docs, verification-report.md, ...), which the Q&A
# and verifier agents are expected to be able to find and read via grep_repo
# just like any other repo content. Excluding it silently let agents treat
# "no grep hit" as proof-of-absence for files grep never had a chance to see.
ALWAYS_IGNORE = {".git", "__pycache__", "node_modules", ".venv", "venv"}


@dataclass
class GrepMatch:
    path: str  # relative to repo_root, posix-style
    line: int
    text: str


def grep(repo_root: Path, pattern: str, *, max_results: int = 50) -> list[GrepMatch]:
    if shutil.which("rg"):
        return _grep_ripgrep(repo_root, pattern, max_results)
    return _grep_python(repo_root, pattern, max_results)


def _grep_ripgrep(repo_root: Path, pattern: str, max_results: int) -> list[GrepMatch]:
    try:
        proc = subprocess.run(
            [
                "rg",
                "--line-number",
                "--no-heading",
                "--max-count",
                "10",
                # ripgrep skips dotdirs by default, which would silently hide
                # .code-atlas/ again even though it's not in ALWAYS_IGNORE —
                # --hidden undoes that, and the globs restore the exclusions
                # ALWAYS_IGNORE encodes for the pure-Python fallback below.
                "--hidden",
                *[f"--glob=!{d}/" for d in ALWAYS_IGNORE],
                pattern,
                ".",
            ],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.TimeoutExpired, OSError):
        return []
    if proc.returncode not in (0, 1):  # 1 = no matches, not a real error
        return []

    matches: list[GrepMatch] = []
    for line in proc.stdout.splitlines():
        parsed = _parse_rg_line(line)
        if parsed:
            matches.append(parsed)
        if len(matches) >= max_results:
            break
    return matches


def _parse_rg_line(line: str) -> GrepMatch | None:
    parts = line.split(":", 2)
    if len(parts) != 3:
        return None
    path, line_no, text = parts
    try:
        return GrepMatch(path=path, line=int(line_no), text=text)
    except ValueError:
        return None


def _grep_python(repo_root: Path, pattern: str, max_results: int) -> list[GrepMatch]:
    try:
        regex = re.compile(pattern)
    except re.error:
        regex = re.compile(re.escape(pattern))

    matches: list[GrepMatch] = []
    for path in sorted(repo_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(repo_root)
        if any(part in ALWAYS_IGNORE for part in rel.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                matches.append(GrepMatch(path=rel.as_posix(), line=i, text=line))
                if len(matches) >= max_results:
                    return matches
    return matches
