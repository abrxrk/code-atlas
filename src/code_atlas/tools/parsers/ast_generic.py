from dataclasses import dataclass
from pathlib import Path

# Best-effort display name only — we don't parse these languages, just count lines.
_EXTENSION_LANGUAGES = {
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".rb": "Ruby",
    ".php": "PHP",
    ".c": "C",
    ".h": "C",
    ".cpp": "C++",
    ".hpp": "C++",
    ".cs": "C#",
    ".swift": "Swift",
}


@dataclass
class GenericModuleInfo:
    path: Path
    line_count: int
    language: str | None


def parse(path: Path) -> GenericModuleInfo | None:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    return GenericModuleInfo(
        path=path,
        line_count=text.count("\n") + 1,
        language=_EXTENSION_LANGUAGES.get(path.suffix),
    )
