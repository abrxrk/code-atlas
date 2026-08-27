from pydantic import BaseModel, ConfigDict

from code_atlas.orchestration.nodes.repo_mapper import RepoMapResult
from code_atlas.orchestration.nodes.tech_stack_detector import TechStack


class EntryPoint(BaseModel):
    description: str
    file: str
    line: int | None = None
    verification_reason: str | None = None  # set once the verifier confirms this claim


class ModuleEdge(BaseModel):
    source: str
    target: str
    verification_reason: str | None = None  # set once the verifier confirms this claim


class UnverifiedClaim(BaseModel):
    """A claim that exhausted MAX_RETRIES without being confirmed — surfaced
    explicitly in verification-report.md rather than silently dropped."""

    claim_type: str  # "entry_point" | "module_edge"
    description: str
    reason: str


class IndexState(BaseModel):
    """Shared state threaded through every node in orchestration/graph.py.

    entry_points/module_edges hold the CURRENT round's candidate claims —
    on the first pass, everything entry_point_agent/module_relationship_agent
    produced; on a retry pass, only the claims the verifier just rejected
    (targeted re-check, not a full redo). Claims the verifier confirms move
    into confirmed_entry_points/confirmed_module_edges permanently. Claims
    still failing after MAX_RETRIES move into unverified_claims permanently
    and are cleared from entry_points/module_edges, which is what lets the
    conditional edge in graph.py detect "nothing left to retry" and route
    to writer.

    entry_point_failure_reasons/module_edge_failure_reasons are index-aligned
    with entry_points/module_edges only while a retry is pending — the
    verifier's rejection reason for each claim, so the entry_point_recheck/
    module_relationship_recheck nodes can build a recheck() prompt that
    explains *why* each claim failed, not just which claims failed.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    repo_root: str
    repo_map: RepoMapResult | None = None
    tech_stack: TechStack | None = None
    entry_points: list[EntryPoint] = []
    module_edges: list[ModuleEdge] = []
    entry_point_failure_reasons: list[str] = []
    module_edge_failure_reasons: list[str] = []
    confirmed_entry_points: list[EntryPoint] = []
    confirmed_module_edges: list[ModuleEdge] = []
    unverified_claims: list[UnverifiedClaim] = []
    retry_count: int = 0
