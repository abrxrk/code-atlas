from pydantic import BaseModel, ConfigDict

from code_atlas.orchestration.nodes.repo_mapper import RepoMapResult
from code_atlas.orchestration.nodes.tech_stack_detector import TechStack


class EntryPoint(BaseModel):
    description: str
    file: str
    line: int | None = None


class ModuleEdge(BaseModel):
    source: str
    target: str


class IndexState(BaseModel):
    """Shared state threaded through every node in orchestration/graph.py."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    repo_root: str
    repo_map: RepoMapResult | None = None
    tech_stack: TechStack | None = None
    entry_points: list[EntryPoint] = []
    module_edges: list[ModuleEdge] = []
