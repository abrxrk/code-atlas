import json
import os
import shutil
import subprocess
import sys
import tempfile

from code_atlas.llm.agent_backend import AgentResult

CLAUDE_CLI = "claude"
MCP_SERVER_NAME = "code-atlas-tools"


class ClaudeCodeBackend:
    def __init__(self, model: str | None = None, repo_root: str | None = None) -> None:
        self.model = model
        self.repo_root = repo_root

    def run(self, prompt: str, *, tools: list[str] | None = None) -> AgentResult:
        command = [CLAUDE_CLI, "-p", prompt, "--output-format", "json"]
        if self.model:
            command += ["--model", self.model]

        mcp_config_path = None
        if tools:
            if self.repo_root is None:
                raise RuntimeError(
                    "ClaudeCodeBackend.run() was called with tools=[...] but no repo_root was "
                    "set. Build the backend via provider_factory.get_agent_backend(role, "
                    "repo_root=...) whenever tool-calling is needed."
                )

            mcp_config = {
                "mcpServers": {
                    MCP_SERVER_NAME: {
                        # Invoke this same interpreter's code_atlas module directly
                        # (sys.executable is an absolute path) rather than relying on
                        # a bare "code-atlas" command being resolvable on whatever PATH
                        # the (possibly long-lived, reused) server process inherited.
                        "command": sys.executable,
                        "args": [
                            "-m",
                            "code_atlas.cli.app",
                            "mcp-serve",
                            "--repo-root",
                            self.repo_root,
                        ],
                    }
                }
            }
            fd, mcp_config_path = tempfile.mkstemp(suffix=".json", prefix="code-atlas-mcp-")
            with os.fdopen(fd, "w") as f:
                json.dump(mcp_config, f)

            allowed_tools = ",".join(f"mcp__{MCP_SERVER_NAME}__{name}" for name in tools)
            command += [
                "--mcp-config",
                mcp_config_path,
                "--strict-mcp-config",
                # Disable the built-in tool set (Read/Bash/Write/...) so bypassPermissions
                # below only ever auto-approves the read-only agent_tools.py functions named
                # in `tools`, not arbitrary filesystem/shell access.
                "--tools",
                "",
                "--allowedTools",
                allowed_tools,
                "--permission-mode",
                "bypassPermissions",
            ]

        # Run from a fresh, empty, non-repo directory rather than whatever cwd this
        # (possibly long-lived, reused) process happens to have. Otherwise the nested
        # `claude` call auto-discovers whatever CLAUDE.md sits at/above the ambient
        # cwd as "project memory" — including, on a re-index, code-atlas's own
        # previously-written CLAUDE.md for repo_root, contaminating what is supposed
        # to be an independent check. Tool access to repo_root itself still works
        # normally, since agent_tools.py takes repo_root as an explicit argument via
        # the MCP server, not via cwd.
        isolated_cwd = tempfile.mkdtemp(prefix="code-atlas-claude-cwd-")
        try:
            proc = self._invoke(command, cwd=isolated_cwd)
        finally:
            if mcp_config_path is not None:
                try:
                    os.remove(mcp_config_path)
                except OSError:
                    pass
            shutil.rmtree(isolated_cwd, ignore_errors=True)

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

        if tools and envelope.get("num_turns", 0) <= 1:
            # A tool-calling call that never actually round-tripped through a tool
            # (num_turns==1 means the model answered on its very first turn) means
            # either the MCP server never started (e.g. an unresolvable command) or
            # the model skipped tool use entirely. Either way, any "evidence" in the
            # response text cannot be trusted — treat it as a hard failure instead of
            # letting a hallucinated verdict pass through as if it were grounded.
            raise RuntimeError(
                "claude CLI was given tools=[...] but made zero real tool calls "
                f"(num_turns={envelope.get('num_turns')}) — the MCP tool server likely failed "
                f"to start. Refusing to trust this response as evidence-grounded.\n"
                f"command={command}\nresult={envelope.get('result')!r}"
            )

        return AgentResult(text=envelope["result"])

    def _invoke(self, command: list[str], *, cwd: str) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"claude CLI not found (looked for '{CLAUDE_CLI}' on PATH). Is it installed?"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"claude CLI timed out after 120s. command={command}") from exc
