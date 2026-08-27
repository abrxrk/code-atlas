from dataclasses import dataclass
from typing import Protocol


@dataclass
class AgentResult:
    text: str


class AgentBackend(Protocol):
    def run(self, prompt: str, *, tools: list[str] | None = None) -> AgentResult:
        """Run one prompt to completion and return its final text.

        `tools` is a list of agent_tools.py function names to make
        available for this call (e.g. ["read_file", "grep_repo"]). Pass
        None for a plain, non-tool-calling call. Any tool-calling call
        requires the backend to have been constructed with a repo_root
        (via provider_factory.get_agent_backend(role, repo_root=...)) —
        agent_tools.py's functions are scoped to a specific repo.
        """
        ...
