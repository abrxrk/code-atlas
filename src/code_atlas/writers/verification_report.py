from __future__ import annotations

from pathlib import Path

from code_atlas.orchestration.state import IndexState
from code_atlas.writers.module_docs import format_entry_point

_OUTPUT_DIRNAME = ".code-atlas"


def write(state: IndexState, repo_root: Path) -> Path:
    """Write .code-atlas/verification-report.md: every confirmed claim plus
    every claim that exhausted MAX_RETRIES without confirmation, with reasons.
    """
    output_dir = repo_root / _OUTPUT_DIRNAME
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "verification-report.md"
    path.write_text(_render(state))
    return path


def _render(state: IndexState) -> str:
    confirmed = len(state.confirmed_entry_points) + len(state.confirmed_module_edges)
    total = confirmed + len(state.unverified_claims)

    lines = ["# Verification report", "", f"{confirmed}/{total} claims independently verified.", ""]

    lines += ["## Confirmed entry points", ""]
    if state.confirmed_entry_points:
        lines += [
            f"- {format_entry_point(ep)} — _reason: {ep.verification_reason}_"
            if ep.verification_reason
            else f"- {format_entry_point(ep)}"
            for ep in state.confirmed_entry_points
        ]
    else:
        lines.append("_None._")

    lines += ["", "## Confirmed module edges", ""]
    if state.confirmed_module_edges:
        lines += [
            f"- `{edge.source}` -> `{edge.target}` — _reason: {edge.verification_reason}_"
            if edge.verification_reason
            else f"- `{edge.source}` -> `{edge.target}`"
            for edge in state.confirmed_module_edges
        ]
    else:
        lines.append("_None._")

    lines += ["", "## Unverified claims (dropped after retries)", ""]
    if state.unverified_claims:
        lines += [f"- **[{claim.claim_type}]** {claim.description} — _reason: {claim.reason}_" for claim in state.unverified_claims]
    else:
        lines.append("_None._")

    lines.append("")
    return "\n".join(lines)
