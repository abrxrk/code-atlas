import uuid
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from code_atlas.orchestration import graph
from code_atlas.server.schemas import (
    IndexCompleteEvent,
    IndexErrorEvent,
    IndexProgressEvent,
    IndexRequest,
    IndexResponse,
    IndexSummary,
)

router = APIRouter()

_OUTPUT_DIRNAME = ".code-atlas"
_STATE_DIRNAME = "state"


@router.post("/index")
def index(request: IndexRequest) -> StreamingResponse:
    return StreamingResponse(_stream_events(request), media_type="text/event-stream")


def _stream_events(request: IndexRequest):
    try:
        final_state = None
        for node_name, state in graph.stream_index(request.repo_root):
            final_state = state
            event = IndexProgressEvent(stage=node_name, retry_count=state.retry_count)
            yield f"data: {event.model_dump_json()}\n\n"

        if final_state is None:
            raise RuntimeError("Indexing graph produced no output.")

        response = IndexResponse(
            session_id=str(uuid.uuid4()),
            summary=IndexSummary(
                file_count=final_state.repo_map.file_count if final_state.repo_map else 0,
                languages=final_state.tech_stack.languages if final_state.tech_stack else [],
                frameworks=final_state.tech_stack.frameworks if final_state.tech_stack else [],
                entry_point_count=len(final_state.confirmed_entry_points),
                module_edge_count=len(final_state.confirmed_module_edges),
                output_paths=_output_paths(Path(request.repo_root)),
            ),
        )
        yield f"data: {IndexCompleteEvent(result=response).model_dump_json()}\n\n"
    except Exception as exc:
        yield f"data: {IndexErrorEvent(message=str(exc)).model_dump_json()}\n\n"


def _output_paths(repo_root: Path) -> list[str]:
    paths: list[Path] = []

    for name in ("CLAUDE.md", "AGENTS.md"):
        candidate = repo_root / name
        if candidate.exists():
            paths.append(candidate)

    output_dir = repo_root / _OUTPUT_DIRNAME
    if output_dir.is_dir():
        for path in sorted(output_dir.rglob("*")):
            if path.is_file() and _STATE_DIRNAME not in path.relative_to(output_dir).parts:
                paths.append(path)

    return [str(path) for path in paths]
