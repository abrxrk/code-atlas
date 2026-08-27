"""The real indexing pipeline: repo_mapper -> tech_stack_detector -> (parallel fan-out) -> writer.

See plan.md "LangGraph Indexing Pipeline". Verification + retry (stage 4)
land in a later build phase; this graph currently ends at `writer`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from code_atlas.llm.provider_factory import get_agent_backend
from code_atlas.orchestration.nodes import entry_point_agent, module_relationship_agent, repo_mapper, tech_stack_detector
from code_atlas.orchestration.nodes.repo_mapper import RepoMapResult
from code_atlas.orchestration.state import IndexState
from code_atlas.store.models import SessionState
from code_atlas.store.session_store import save_session
from code_atlas.writers.agents_md import write as write_agents_md
from code_atlas.writers.claude_md import write as write_claude_md
from code_atlas.writers.context import DirectoryEntry, RepoContext, TechStackSummary
from code_atlas.writers.module_docs import format_entry_point, write as write_module_docs


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


def _writer_node(state: IndexState) -> dict:
    repo_root = Path(state.repo_root)
    ctx = _build_repo_context(state, repo_root)

    write_claude_md(ctx, repo_root)
    write_agents_md(ctx, repo_root)
    write_module_docs(state, repo_root)

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


def _build_repo_context(state: IndexState, repo_root: Path) -> RepoContext:
    stack = state.tech_stack
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
        entry_points=[format_entry_point(ep) for ep in state.entry_points],
        verification_summary=None,  # verification lands in Phase 4
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
    builder.add_node("writer", _writer_node)

    builder.add_edge(START, "repo_mapper")
    builder.add_edge("repo_mapper", "tech_stack_detector")
    builder.add_edge("tech_stack_detector", "entry_point_agent")
    builder.add_edge("tech_stack_detector", "module_relationship_agent")
    builder.add_edge("entry_point_agent", "writer")
    builder.add_edge("module_relationship_agent", "writer")
    builder.add_edge("writer", END)

    return builder


graph = _build_graph().compile()


def run_index(repo_root: str) -> IndexState:
    final_state = graph.invoke(IndexState(repo_root=repo_root))
    return IndexState.model_validate(final_state)
