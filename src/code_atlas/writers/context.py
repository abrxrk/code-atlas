from dataclasses import dataclass, field


@dataclass
class TechStackSummary:
    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    build_tools: list[str] = field(default_factory=list)
    run_commands: list[str] = field(default_factory=list)
    notes: str | None = None


@dataclass
class DirectoryEntry:
    name: str
    file_count: int


@dataclass
class RepoContext:
    """Canonical data both CLAUDE.md and AGENTS.md render from.

    Fields that later phases populate (entry_points, verification_summary)
    stay empty/None until then — the template omits those sections rather
    than rendering a fabricated placeholder.
    """

    repo_name: str
    file_count: int
    tech_stack: TechStackSummary
    directories: list[DirectoryEntry] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    verification_summary: str | None = None
