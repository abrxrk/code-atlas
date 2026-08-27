"""The real indexing pipeline: repo_mapper -> tech_stack_detector -> (parallel
fan-out) -> verifier -> (retry loop | writer).

See plan.md "LangGraph Indexing Pipeline". entry_point_agent and
module_relationship_agent's claims are never trusted directly — they both
feed into `verifier`, which independently re-checks each claim against the
real source (tools/agent_tools.py) before it can become a confirmed_* claim.
Claims the verifier rejects loop back through entry_point_recheck/
module_relationship_recheck (targeted re-check of just the flagged claims)
and back to verifier, bounded by retry_policy.MAX_RETRIES; claims still
failing once that bound is hit are surfaced in unverified_claims instead of
being silently dropped or retried forever.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from code_atlas.llm.provider_factory import get_agent_backend
from code_atlas.orchestration.nodes import entry_point_agent, module_relationship_agent, repo_mapper, tech_stack_detector
from code_atlas.orchestration.nodes.repo_mapper import RepoMapResult
from code_atlas.orchestration.nodes.verifier import verify_entry_points, verify_module_edges
from code_atlas.orchestration.retry_policy import MAX_RETRIES
from code_atlas.orchestration.state import IndexState, UnverifiedClaim
from code_atlas.store.models import SessionState, VerificationClaim
from code_atlas.store.session_store import save_session, save_verification_claims
from code_atlas.writers.agents_md import write as write_agents_md
from code_atlas.writers.claude_md import write as write_claude_md
from code_atlas.writers.context import DirectoryEntry, RepoContext, TechStackSummary
from code_atlas.writers.module_docs import format_entry_point, write as write_module_docs
from code_atlas.writers.verification_report import write as write_verification_report

_VERIFIER_TOOLS = ["read_file", "grep_repo"]


def _repo_mapper_node(state: IndexState) -> dict:
    repo_map = repo_mapper.run(Path(state.repo_root))
    return {"repo_map": repo_map}


def _tech_stack_detector_node(state: IndexState) -> dict:
    tech_stack = tech_stack_detector.run(state.repo_map)
    return {"tech_stack": tech_stack}


def _entry_point_agent_node(state: IndexState) -> dict:
    backend = get_agent_backend("analysis")
    entry_points = entry_point_agent.run(state.repo_map, backend)
    return {"entry_points": entry_points}


def _module_relationship_agent_node(state: IndexState) -> dict:
    backend = get_agent_backend("analysis")
    module_edges = module_relationship_agent.run(state.repo_map, backend)
    return {"module_edges": module_edges}


def _verifier_node(state: IndexState) -> dict:
    backend = get_agent_backend("verifier", repo_root=state.repo_root)

    ep_results = verify_entry_points(state.repo_root, state.entry_points, backend)
    edge_results = verify_module_edges(state.repo_root, state.module_edges, backend)

    confirmed_entry_points = list(state.confirmed_entry_points)
    confirmed_module_edges = list(state.confirmed_module_edges)
    failed_entry_points: list[tuple] = []
    failed_module_edges: list[tuple] = []

    for claim, verified, reason in ep_results:
        if verified:
            confirmed_entry_points.append(claim.model_copy(update={"verification_reason": reason}))
        else:
            failed_entry_points.append((claim, reason))

    for claim, verified, reason in edge_results:
        if verified:
            confirmed_module_edges.append(claim.model_copy(update={"verification_reason": reason}))
        else:
            failed_module_edges.append((claim, reason))

    unverified_claims = list(state.unverified_claims)
    retry_count = state.retry_count
    next_entry_points: list = []
    next_module_edges: list = []
    next_entry_point_reasons: list[str] = []
    next_module_edge_reasons: list[str] = []

    if failed_entry_points or failed_module_edges:
        if retry_count < MAX_RETRIES:
            next_entry_points = [ep for ep, _ in failed_entry_points]
            next_entry_point_reasons = [reason for _, reason in failed_entry_points]
            next_module_edges = [edge for edge, _ in failed_module_edges]
            next_module_edge_reasons = [reason for _, reason in failed_module_edges]
            retry_count += 1
        else:
            for ep, reason in failed_entry_points:
                unverified_claims.append(
                    UnverifiedClaim(claim_type="entry_point", description=format_entry_point(ep), reason=reason)
                )
            for edge, reason in failed_module_edges:
                unverified_claims.append(
                    UnverifiedClaim(claim_type="module_edge", description=f"{edge.source} -> {edge.target}", reason=reason)
                )

    return {
        "confirmed_entry_points": confirmed_entry_points,
        "confirmed_module_edges": confirmed_module_edges,
        "unverified_claims": unverified_claims,
        "entry_points": next_entry_points,
        "module_edges": next_module_edges,
        "entry_point_failure_reasons": next_entry_point_reasons,
        "module_edge_failure_reasons": next_module_edge_reasons,
        "retry_count": retry_count,
    }


def _entry_point_recheck_node(state: IndexState) -> dict:
    backend = get_agent_backend("analysis")
    failed = list(zip(state.entry_points, state.entry_point_failure_reasons, strict=True))
    entry_points = entry_point_agent.recheck(state.repo_root, failed, backend)
    return {"entry_points": entry_points}


def _module_relationship_recheck_node(state: IndexState) -> dict:
    backend = get_agent_backend("analysis")
    failed = list(zip(state.module_edges, state.module_edge_failure_reasons, strict=True))
    module_edges = module_relationship_agent.recheck(state.repo_root, failed, backend)
    return {"module_edges": module_edges}


def _route_after_verifier(state: IndexState) -> str | list[str]:
    targets = []
    if state.entry_points:
        targets.append("entry_point_recheck")
    if state.module_edges:
        targets.append("module_relationship_recheck")
    return targets or "writer"


def _writer_node(state: IndexState) -> dict:
    repo_root = Path(state.repo_root)
    ctx = _build_repo_context(state, repo_root)

    write_claude_md(ctx, repo_root)
    write_agents_md(ctx, repo_root)
    write_module_docs(state, repo_root)
    write_verification_report(state, repo_root)
    save_verification_claims(repo_root, _combined_verification_claims(state))

    save_session(
        repo_root,
        SessionState(
            repo_root=str(repo_root),
            indexed_at=datetime.now(UTC).isoformat(),
            file_count=state.repo_map.file_count,
            languages=state.tech_stack.languages,
            frameworks=state.tech_stack.frameworks,
        ),
    )
    return {}


def _combined_verification_claims(state: IndexState) -> list[VerificationClaim]:
    claims = [
        VerificationClaim(
            claim_type="entry_point",
            description=format_entry_point(ep),
            verified=True,
            reason=ep.verification_reason or "",
        )
        for ep in state.confirmed_entry_points
    ]
    claims += [
        VerificationClaim(
            claim_type="module_edge",
            description=f"{edge.source} -> {edge.target}",
            verified=True,
            reason=edge.verification_reason or "",
        )
        for edge in state.confirmed_module_edges
    ]
    claims += [
        VerificationClaim(claim_type=c.claim_type, description=c.description, verified=False, reason=c.reason)
        for c in state.unverified_claims
    ]
    return claims


def _build_repo_context(state: IndexState, repo_root: Path) -> RepoContext:
    stack = state.tech_stack
    confirmed = len(state.confirmed_entry_points) + len(state.confirmed_module_edges)
    total = confirmed + len(state.unverified_claims)
    verification_summary = (
        f"{confirmed}/{total} claims independently verified; see verification-report.md" if total else None
    )
    return RepoContext(
        repo_name=_repo_name(state.repo_map, repo_root),
        file_count=state.repo_map.file_count,
        tech_stack=TechStackSummary(
            languages=stack.languages,
            frameworks=stack.frameworks,
            build_tools=stack.build_tools,
            run_commands=stack.run_commands,
            notes=stack.notes,
        ),
        directories=sorted(
            (DirectoryEntry(name=name, file_count=len(files)) for name, files in state.repo_map.clusters.items()),
            key=lambda entry: entry.name,
        ),
        entry_points=[format_entry_point(ep) for ep in state.confirmed_entry_points],
        verification_summary=verification_summary,
    )


def _repo_name(repo_map: RepoMapResult, root: Path) -> str:
    for manifest in repo_map.manifests:
        if manifest.name:
            return manifest.name
    return root.name


def _build_graph() -> StateGraph:
    builder = StateGraph(IndexState)

    builder.add_node("repo_mapper", _repo_mapper_node)
    builder.add_node("tech_stack_detector", _tech_stack_detector_node)
    builder.add_node("entry_point_agent", _entry_point_agent_node)
    builder.add_node("module_relationship_agent", _module_relationship_agent_node)
    builder.add_node("verifier", _verifier_node)
    builder.add_node("entry_point_recheck", _entry_point_recheck_node)
    builder.add_node("module_relationship_recheck", _module_relationship_recheck_node)
    builder.add_node("writer", _writer_node)

    builder.add_edge(START, "repo_mapper")
    builder.add_edge("repo_mapper", "tech_stack_detector")
    builder.add_edge("tech_stack_detector", "entry_point_agent")
    builder.add_edge("tech_stack_detector", "module_relationship_agent")
    builder.add_edge("entry_point_agent", "verifier")
    builder.add_edge("module_relationship_agent", "verifier")

    builder.add_conditional_edges(
        "verifier",
        _route_after_verifier,
        ["entry_point_recheck", "module_relationship_recheck", "writer"],
    )
    builder.add_edge("entry_point_recheck", "verifier")
    builder.add_edge("module_relationship_recheck", "verifier")

    builder.add_edge("writer", END)

    return builder


graph = _build_graph().compile()


def run_index(repo_root: str) -> IndexState:
    final_state = graph.invoke(IndexState(repo_root=repo_root), {"recursion_limit": 100})
    return IndexState.model_validate(final_state)
