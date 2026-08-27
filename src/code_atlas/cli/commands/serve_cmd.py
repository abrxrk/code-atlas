import uvicorn

from code_atlas.cli.ui import print_info


def run() -> None:
    """Run the local server in the foreground, for debugging.

    code-atlas normally runs indexing/Q&A through a detached background
    server; this runs it in the foreground instead so you can see its
    logs directly.
    """
    print_info("Starting code-atlas server in the foreground on http://127.0.0.1:8420 ...")
    uvicorn.run("code_atlas.server.app:create_app", factory=True, host="127.0.0.1", port=8420)
