import json
import subprocess

from code_atlas.llm.agent_backend import AgentResult

CLAUDE_CLI = "claude"


class ClaudeCodeBackend:
    def __init__(self, model: str | None = None) -> None:
        self.model = model

    def run(self, prompt: str, *, tools: list[str] | None = None) -> AgentResult:
        command = [CLAUDE_CLI, "-p", prompt, "--output-format", "json"]
        if self.model:
            command += ["--model", self.model]

        try:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=120)
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"claude CLI not found (looked for '{CLAUDE_CLI}' on PATH). Is it installed?"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"claude CLI timed out after 120s. command={command}") from exc

        if proc.returncode != 0:
            raise RuntimeError(
                f"claude CLI exited with code {proc.returncode}.\n"
                f"command={command}\nstdout={proc.stdout}\nstderr={proc.stderr}"
            )

        try:
            envelope = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"claude CLI stdout was not valid JSON.\n"
                f"command={command}\nstdout={proc.stdout}\nstderr={proc.stderr}"
            ) from exc

        if envelope.get("is_error") or "result" not in envelope:
            raise RuntimeError(
                f"claude CLI reported an error or an unexpected JSON shape (missing 'result').\n"
                f"command={command}\nstdout={proc.stdout}\nstderr={proc.stderr}"
            )

        return AgentResult(text=envelope["result"])
