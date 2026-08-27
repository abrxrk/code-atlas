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
        None for a plain, non-tool-calling call.
        """
        ...
