import uuid
from pathlib import Path

from fastapi import APIRouter

from code_atlas.orchestration import graph
from code_atlas.server.schemas import IndexRequest, IndexResponse, IndexSummary

router = APIRouter()

_OUTPUT_DIRNAME = ".code-atlas"
_STATE_DIRNAME = "state"


@router.post("/index")
def index(request: IndexRequest) -> IndexResponse:
    state = graph.run_index(request.repo_root)

    return IndexResponse(
        session_id=str(uuid.uuid4()),
        summary=IndexSummary(
            file_count=state.repo_map.file_count if state.repo_map else 0,
            languages=state.tech_stack.languages if state.tech_stack else [],
            frameworks=state.tech_stack.frameworks if state.tech_stack else [],
            entry_point_count=len(state.entry_points),
            module_edge_count=len(state.module_edges),
            output_paths=_output_paths(Path(request.repo_root)),
        ),
    )


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
