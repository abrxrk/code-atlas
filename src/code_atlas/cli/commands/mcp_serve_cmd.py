import typer


def run(
    repo_root: str = typer.Option(..., "--repo-root", help="Repo root to scope every tool call to."),
) -> None:
    """Run the code-atlas MCP tools server (stdio transport).

    Internal command: launched as a subprocess by the `claude` CLI itself
    via --mcp-config (see llm/claude_code_backend.py), not meant to be run
    directly by a human.
    """
    from code_atlas.tools import mcp_server

    mcp_server._repo_root = repo_root
    mcp_server.mcp.run(transport="stdio")
