"""One-shot Q&A over an indexed (or unindexed) repo.

Reuses the exact tools/trust mechanism the verifier uses (tools/agent_tools.py)
so answers are grounded the same way confirmed_* claims are during indexing:
the agent must actually look at real source via read_file/grep_repo/etc.
rather than guessing from the question or from .code-atlas/index.md alone.

Not a LangGraph StateGraph — a single tool-calling backend call is enough for
this shape of task, so this module is a plain function despite the package's
name (orchestration/) grouping it with graph.py.
"""

from datetime import UTC, datetime
from pathlib import Path

from code_atlas.llm.provider_factory import get_agent_backend
from code_atlas.store import session_store
from code_atlas.store.models import QAHistoryEntry

_TOOLS = ["read_file", "grep_repo", "list_dir", "list_modules", "get_module_doc"]
_INDEX_PATH = Path(".code-atlas") / "index.md"


def answer_question(repo_root: str, question: str) -> str:
    prompt = _build_prompt(repo_root, question)
    backend = get_agent_backend("qa", repo_root=repo_root)
    answer = backend.run(prompt, tools=_TOOLS).text
    session_store.append_qa_history(
        Path(repo_root),
        QAHistoryEntry(question=question, answer=answer, asked_at=datetime.now(UTC).isoformat()),
    )
    return answer


def _build_prompt(repo_root: str, question: str) -> str:
    index_content = _read_index(repo_root)

    if index_content is not None:
        context_block = (
            "This repo has already been indexed. Here is .code-atlas/index.md, a "
            "table-of-contents of the modules code-atlas found — use it as a starting "
            "map, then use list_modules/get_module_doc to read the relevant module "
            "doc(s), and read_file/grep_repo to confirm claims against real source "
            "before answering:\n\n"
            f"{index_content}"
        )
    else:
        context_block = (
            "This repo has NOT been indexed yet — there is no .code-atlas/ directory. "
            "You have no table-of-contents or module docs to start from. Explore the "
            "raw source directly: use list_dir to see what's there and grep_repo/"
            "read_file to find and confirm the relevant code. If your access is too "
            "limited to answer confidently, say so honestly rather than guessing."
        )

    return (
        "You are answering a question about a codebase using tools that give you "
        "real access to its files. Do NOT guess or answer from general knowledge of "
        "similar codebases — find actual evidence in this repo before answering.\n\n"
        f"{context_block}\n\n"
        f"Question: {question}\n\n"
        "Use read_file, grep_repo, list_dir, list_modules, and get_module_doc as "
        "needed to find real evidence. In your final answer, cite the actual "
        "file path (and line number, when relevant) where you found the evidence "
        "for each claim you make. If you cannot find enough evidence to answer "
        "confidently, say so honestly instead of guessing."
    )


def _read_index(repo_root: str) -> str | None:
    path = Path(repo_root) / _INDEX_PATH
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None
