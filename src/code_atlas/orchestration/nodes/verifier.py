"""Independently re-checks entry_point_agent/module_relationship_agent claims
against actual source, using the same read_file/grep_repo tools the Q&A agent
uses (tools/agent_tools.py). This is the anti-hallucination gate: a claim is
never trusted just because a prior LLM call produced it — it only becomes a
confirmed_entry_point/confirmed_module_edge in IndexState once a fresh backend
call, with tool access to the real repo, has actually looked at the cited
file and said so. Any parse failure or backend exception fails closed
(verified=False), never open.
"""

import json
import re
from concurrent.futures import ThreadPoolExecutor

from code_atlas.llm.agent_backend import AgentBackend
from code_atlas.orchestration.state import EntryPoint, ModuleEdge

_CODE_FENCE_RE = re.compile(r"^```[a-zA-Z]*\n|\n```$")
_TOOLS = ["read_file", "grep_repo"]
_MAX_WORKERS = 8


def verify_entry_points(
    repo_root: str, entry_points: list[EntryPoint], backend: AgentBackend
) -> list[tuple[EntryPoint, bool, str]]:
    if not entry_points:
        return []
    verdicts = _run_parallel(
        [lambda claim=claim: _verify_claim(repo_root, _build_entry_point_prompt(claim), backend) for claim in entry_points]
    )
    return list(zip(entry_points, [v for v, _ in verdicts], [r for _, r in verdicts]))


def verify_module_edges(
    repo_root: str, module_edges: list[ModuleEdge], backend: AgentBackend
) -> list[tuple[ModuleEdge, bool, str]]:
    if not module_edges:
        return []
    verdicts = _run_parallel(
        [lambda claim=claim: _verify_claim(repo_root, _build_module_edge_prompt(claim), backend) for claim in module_edges]
    )
    return list(zip(module_edges, [v for v, _ in verdicts], [r for _, r in verdicts]))


def _run_parallel(calls: list) -> list[tuple[bool, str]]:
    """Run independent verification calls concurrently (each is its own subprocess/HTTP
    call, so this is pure I/O parallelism) while preserving `calls` order in the result —
    each `claude -p` invocation can take anywhere from ~4-90s, and a repo with many claims
    verified strictly serially can approach or exceed the CLI's fixed httpx timeout."""
    with ThreadPoolExecutor(max_workers=min(_MAX_WORKERS, len(calls))) as pool:
        return list(pool.map(lambda call: call(), calls))


def _verify_claim(repo_root: str, prompt: str, backend: AgentBackend) -> tuple[bool, str]:
    try:
        response = backend.run(prompt, tools=_TOOLS)
    except Exception as exc:  # backend/provider failures shouldn't crash the whole run
        return False, f"verification error: backend call failed: {exc}"

    parsed = _parse_verdict(response.text)
    if parsed is None:
        return False, "verification error: could not parse verifier response as JSON"

    return parsed


def _build_entry_point_prompt(claim: EntryPoint) -> str:
    line_clause = f"at line {claim.line}" if claim.line is not None else "(no specific line given — judge the file in general)"
    return (
        "You are independently verifying a claim made by another AI about a codebase. "
        "Do NOT trust the claim — actually read the cited file yourself using the read_file "
        "tool (and grep_repo if useful) before answering.\n\n"
        "Claim: this is an entry point of the codebase.\n"
        f"  File: {claim.file}\n"
        f"  Line: {line_clause}\n"
        f"  Description: {claim.description}\n\n"
        "Read the file and confirm whether this description is actually accurate for that "
        "file/line — not merely that the file exists. Does the file really contain an entry "
        "point (a main function, CLI command, HTTP route, `if __name__ == \"__main__\"` block, "
        "etc.) matching the description?\n\n"
        "Reply with ONLY JSON, no markdown, no code fences, no explanation outside the JSON:\n"
        '{"verified": true or false, "reason": "short string explaining why"}'
    )


def _build_module_edge_prompt(claim: ModuleEdge) -> str:
    return (
        "You are independently verifying a claim made by another AI about a codebase. "
        "Do NOT trust the claim — actually read the source file yourself using the read_file "
        "tool (and grep_repo if useful) before answering.\n\n"
        f"Claim: the file '{claim.source}' imports the file '{claim.target}'.\n\n"
        f"Read '{claim.source}' and confirm whether it genuinely imports '{claim.target}' "
        "(directly, by whatever import mechanism the language uses) — not just that both "
        "files exist.\n\n"
        "Reply with ONLY JSON, no markdown, no code fences, no explanation outside the JSON:\n"
        '{"verified": true or false, "reason": "short string explaining why"}'
    )


def _parse_verdict(text: str) -> tuple[bool, str] | None:
    cleaned = _CODE_FENCE_RE.sub("", text.strip()).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict) or "verified" not in data:
        return None

    verified = data["verified"]
    if not isinstance(verified, bool):
        return None

    reason = data.get("reason", "")
    if not isinstance(reason, str):
        reason = str(reason)

    return verified, reason
