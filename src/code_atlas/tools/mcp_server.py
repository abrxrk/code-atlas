"""MCP server exposing agent_tools.py functions for the Claude Code CLI backend.

Launched as a subprocess by the `claude` CLI itself via --mcp-config (see
llm/claude_code_backend.py), not something a human runs directly — though
`code-atlas mcp-serve --repo-root <path>` is the registered CLI command that
starts it. Every tool call here is bound to the --repo-root given at startup;
repo_root is never an LLM-visible parameter, so the model can't point these
tools at an arbitrary path.
"""

import argparse

from mcp.server.fastmcp import FastMCP

from code_atlas.tools import agent_tools

mcp = FastMCP("code-atlas-tools")

_repo_root: str | None = None


@mcp.tool()
def read_file(relative_path: str) -> str:
    """Read a file's contents from the repo, given a path relative to the repo root."""
    return agent_tools.read_file(_repo_root, relative_path)


@mcp.tool()
def grep_repo(pattern: str) -> str:
    """Search the repo for a regex pattern, returning matching lines with file:line."""
    return agent_tools.grep_repo(_repo_root, pattern)


@mcp.tool()
def list_dir(relative_path: str = "") -> str:
    """List the entries of a directory in the repo, given a path relative to the repo root."""
    return agent_tools.list_dir(_repo_root, relative_path)


@mcp.tool()
def list_modules() -> str:
    """List the module doc names already written by `code-atlas index`."""
    return agent_tools.list_modules(_repo_root)


@mcp.tool()
def get_module_doc(module_name: str) -> str:
    """Read a module doc written by `code-atlas index`, given its module name."""
    return agent_tools.get_module_doc(_repo_root, module_name)


def main() -> None:
    global _repo_root
    parser = argparse.ArgumentParser(prog="code-atlas-mcp-server")
    parser.add_argument("--repo-root", required=True, help="Repo root to scope every tool call to.")
    args = parser.parse_args()
    _repo_root = args.repo_root
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
