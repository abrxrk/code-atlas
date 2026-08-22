# CLAUDE.md

This repo builds `code-atlas`, a terminal tool that indexes other codebases. This file is about working *on* code-atlas itself.

## Start here

Read [plan.md](./plan.md) first — it has the full architecture, package layout, LangGraph pipeline design, and build order. This file is just a pointer plus fast-lookup facts; don't duplicate plan.md's content here, keep it current instead.

## Current stage

Greenfield — no code written yet. Follow the build order in plan.md § "Suggested build order":
1. CLI skeleton (Typer), config loader, `doctor` command
2. Deterministic core (fs_walk, manifest parsers, AST parsers, repo_mapper/tech_stack_detector nodes, writer templates) — no LangGraph yet
3. Docker + Mongo (docker_manager, repository.py)
4. Real LangGraph orchestration + parallel agents + FastAPI/SSE
5. Verifier + retry loop
6. Q&A (agent_tools.py, create_react_agent, REPL)
7. Polish + PyPI packaging

## Locked-in decisions (don't relitigate without discussion)

- Fully local, no hosted backend, no accounts. Only outbound network calls are to the user's own LLM provider.
- Terminal-only for v1, no web frontend.
- Python-native distribution (`uvx`/`pipx`), not an npx/Node wrapper.
- MongoDB via Docker, managed by the tool itself (`mongodb/mongodb-atlas-local` image) — not a native Mongo install, not hosted Atlas.
- No embeddings/RAG for v1 Q&A — agentic tool-calling only (`create_react_agent` + `agent_tools.py`).
- Incremental re-index is explicitly out of scope for v1, but schema (per-file hash, cluster id) is shaped to support it later.

## Key seams

- `db/repository.py` — the only module allowed to import motor/pymongo. Everything else goes through typed DAO calls.
- `tools/agent_tools.py` — shared between the verifier and the Q&A agent; keep it that way so "verify" and "answer" use the same trust mechanism.
- `llm/provider_factory.py` — `get_chat_model(role)` where role is `analysis`/`verifier`/`qa`, so config can route cheaper vs. stronger models per role.

## Testing conventions

Unit tests use a fake chat model (no real API calls). DB tests use `mongomock`/`mongomock-motor` by default; real-container tests are marked `@pytest.mark.docker`. See plan.md § "Testing / Verification Plan" for the full breakdown, including the integration fixture repo with a deliberately misleading docstring used to prove the verifier catches false claims.
