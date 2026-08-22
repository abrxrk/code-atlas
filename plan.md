# code-atlas — Terminal Codebase-Understanding Agent

## Context

Claude Code's `/init` produces a shallow CLAUDE.md summary. The goal here is a standalone tool, `code-atlas`, that a developer runs inside any repo to produce a much deeper, **verified** map of the codebase — tech stack, entry points, execution flows, module relationships — written out as structured files that other coding agents (Claude Code, Codex, Cursor, etc.) read to work more effectively in that repo. It also gives the developer a terminal Q&A interface to ask questions about the codebase directly ("how does auth work?").

This is a greenfield project (working directory is currently empty) — this plan defines the initial architecture and build order, not a change to existing code.

### Key decisions locked in during planning
- **Fully local, like Claude Code.** No hosted backend operated by us, no accounts/login. The CLI, orchestration, and DB all run on the user's machine. The only network calls are outbound to the user's own LLM provider.
- **No Next.js / web frontend for v1.** Terminal-only.
- **Multi-provider LLM access, user's own API key** (Anthropic + OpenAI at minimum), configured locally.
- **MongoDB, local, Docker-managed by the tool itself** (not a pre-existing install, not hosted Atlas).
- **Distribution: Python-native**, not npx/Node. Every other piece of the stack (LangGraph, FastAPI, Mongo drivers) is Python — a Node wrapper that bootstraps a Python venv adds a second runtime and a class of "which Python did it find" bugs for zero benefit. Ship as `code-atlas` on PyPI, run via `uvx code-atlas` (ephemeral, npx-equivalent ergonomics) or `pipx install code-atlas` (persistent).

## Architecture

**CLI (Typer) → local FastAPI server (localhost, detached subprocess) → LangGraph orchestration → MongoDB (Docker-managed) + outbound LLM calls.**

The CLI never imports orchestration code directly — it only talks to the local FastAPI server over HTTP. This decouples the terminal UI from the agent pipeline, which is the concrete reason FastAPI earns its place in the stack for a single-user local tool: it supports streaming (SSE) progress/Q&A naturally, and lets the same backend potentially serve other future clients (IDE extension, dashboard) without rearchitecting.

## Package Layout

```
code-atlas/
  pyproject.toml                      # [project.scripts] code-atlas = "code_atlas.cli.app:main"
  src/code_atlas/
    cli/
      app.py                          # Typer app: index / ask / serve / doctor / config
      commands/{index_cmd,ask_cmd,doctor_cmd,config_cmd}.py
      progress.py                     # rich.Live renderer fed by SSE
      repl.py                         # interactive Q&A loop
    config/
      settings.py                     # pydantic-settings: ~/.code-atlas/config.toml + env overrides
      paths.py
    server/
      app.py                          # FastAPI app factory
      routes/{index_routes,qa_routes,health_routes}.py
      process.py                      # spawn/detect detached uvicorn subprocess via pidfile+port lockfile
      schemas.py                      # HTTP request/response models
    orchestration/
      state.py                        # IndexState (pydantic) shared across graph nodes
      graph.py                        # indexing StateGraph: nodes, edges, conditional retry
      qa_graph.py                     # Q&A graph (LangGraph create_react_agent)
      nodes/
        repo_mapper.py
        tech_stack_detector.py
        entry_point_agent.py
        module_relationship_agent.py
        verifier.py
        writer.py
      retry_policy.py
    tools/
      fs_walk.py                      # .gitignore-aware walk (pathspec)
      grep.py                         # ripgrep subprocess wrapper + pure-python fallback
      parsers/
        manifest_parsers.py           # package.json, pyproject.toml, requirements*.txt, go.mod, Cargo.toml, pom.xml, Gemfile, composer.json
        ast_python.py                 # stdlib ast import/def extraction
        ast_js_ts.py                  # tree-sitter import/export/route extraction
        ast_generic.py
      agent_tools.py                  # read_file/grep_repo/list_dir/list_modules/get_module_doc — shared by verifier AND Q&A agent
    llm/
      provider_factory.py             # get_chat_model(role) -> langchain BaseChatModel (anthropic/openai)
    db/
      client.py                       # motor client singleton
      models.py                       # pydantic models mirroring collections
      repository.py                   # ONLY module that imports motor/pymongo — all DB access is typed DAO calls
    infra/
      docker_manager.py               # docker SDK: ensure_mongo_running(), pull/create/health-check
      doctor.py
    writers/
      templates/*.md.j2
      claude_md.py / agents_md.py / module_docs.py / index_manifest.py
  tests/
    unit/{nodes,tools,writers}/
    integration/fixtures/sample_repo/
    integration/test_full_pipeline.py
```

Key contracts:
- `repository.py` is the single DB seam — everything else calls typed functions, keeping tests mockable and the DB swappable.
- `agent_tools.py` is shared between the verifier and the Q&A agent, so "verify against source" and "answer against source" use the same trust mechanism.
- `provider_factory.get_chat_model(role)` takes a role (`analysis`/`verifier`/`qa`), so config can assign cheaper models to bulk analysis and stronger ones to verification/Q&A.

## LangGraph Indexing Pipeline

1. **`repo_mapper`** (deterministic) — walks tree respecting `.gitignore`, builds file inventory + top-level clusters.
2. **`tech_stack_detector`** (manifest parsing + one LLM call to disambiguate) — produces languages/frameworks/build tools/run commands. Gates stage 2, since downstream agents need to know what kind of app they're looking at.
3. **Parallel fan-out** — `entry_point_agent` and `module_relationship_agent` run concurrently, each internally map-reducing over clusters (never feeding a whole repo into one LLM call). This is the "specialized agents in parallel" requirement.
4. **`verifier`** — for every claim emitted in stage 3 (an entry point, a module purpose, a dependency edge), re-opens the cited file via `read_file`/`grep_repo` and checks the citation is real. This is the anti-hallucination mechanism and the core differentiator from `/init`.
   - Conditional edge: claims that fail route back to the specific agent that produced them (targeted re-check of just the flagged claims, not a full redo), bounded by `MAX_RETRIES` (default 2). Claims still failing after retries are marked `unverified_after_retries` and surfaced explicitly in the output rather than silently dropped or endlessly retried.
5. **`writer`** — Jinja2 templating + one LLM call for top-level prose synthesis; renders CLAUDE.md/AGENTS.md/`.code-atlas/*` and persists via `repository.py`.

## Q&A — agentic tool-calling, no embeddings for v1

Use LangGraph's `create_react_agent` wired to `agent_tools.py`, with `.code-atlas/index.md` preloaded as a table of contents. The agent decides which module docs/source files to open per question, citing real file:line evidence — consistent with the verifier's own approach. Embedding-based RAG (local `fastembed`, stored in Mongo) is a deliberate fast-follow, not v1: at MVP scale, agentic exploration is simpler, cheaper (no second embedding provider), and more verifiable, and the Mongo image chosen below already supports adding vector search later without a rearchitecture.

## MongoDB

Use `mongodb/mongodb-atlas-local` Docker image (superset of community Mongo; costs a larger initial pull, but avoids a container/data migration when embeddings are added later). Managed via the `docker` Python SDK (not docker-compose) — container `code-atlas-mongo`, volume `code-atlas-mongo-data`, port `27019`.

Collections: `repos`, `sessions`, `files` (includes `sha256`+`cluster_id` to support future incremental re-index), `modules`, `module_edges`, `entry_points`, `verification_claims` (audit trail), `qa_history`. API keys/provider config stay in `~/.code-atlas/config.toml`, never in Mongo.

## CLI UX Flow

1. `code-atlas index [path]` (defaults to cwd).
2. First run: no `~/.code-atlas/config.toml` → prompt for provider + API key, write config (`chmod 600`).
3. Preflight: Docker reachable → `ensure_mongo_running()`. If Docker is missing, fail clearly with install instructions (Mongo storage is load-bearing, not optional in v1).
4. Ensure local FastAPI server running (pidfile+port lockfile at `~/.code-atlas/server.json`); spawn detached `uvicorn` subprocess if not, logs to `~/.code-atlas/logs/server.log`.
5. `POST /index` → `session_id` → SSE progress stream → `rich.Live` table (one row per graph node: queued/running/verifying/retrying/done).
6. On completion: summary (files scanned, tech stack, entry points, verification pass rate, output paths) → drops into REPL, which calls `POST /ask` (streamed).
7. `code-atlas ask "question"` for one-shot/scripted use; `code-atlas serve` (foreground, debugging); `code-atlas doctor`/`config` utilities.
8. Incremental re-index is an explicit **non-goal for v1** — schema is shaped (per-file hash, cluster id) so it's additive later, not a rewrite.

## Output files

`CLAUDE.md` and `AGENTS.md` are rendered from one canonical `RepoContext` model + one base Jinja2 template (AGENTS.md is the plain render; CLAUDE.md is the same render plus an optional Claude-specific append block) so they can't drift apart. Kept small (few-thousand-token budget): project purpose, tech stack table, top-level directory map, entry points table, a "how to go deeper" pointer into `.code-atlas/`, and a verification transparency line (e.g. "N/M claims independently verified; see verification-report.md") — the concrete evidence of the differentiator vs `/init`.

`.code-atlas/` (auto-gitignored by default): `index.md` (module table of contents), `modules/<slug>.md` (per-module deep docs with evidence), `entry-points.md`, `dependency-graph.json`, `verification-report.md`, `session.json` (for staleness detection).

## Suggested build order

1. **Skeleton**: CLI scaffold (Typer), config loader, `doctor` command, package layout — no agents yet.
2. **Deterministic core**: `fs_walk`, manifest parsers, AST parsers, `repo_mapper` + `tech_stack_detector` nodes running standalone (no LangGraph yet), writer templates producing a first CLAUDE.md/AGENTS.md from just these two.
3. **Docker + Mongo**: `docker_manager`, `repository.py`, wire persistence into the pipeline above.
4. **LangGraph orchestration**: build the real graph, add `entry_point_agent`/`module_relationship_agent` running in parallel, wire FastAPI server + SSE progress + CLI as an HTTP client of it.
5. **Verifier + retry loop**: the anti-hallucination mechanism — this is the product's core claim, worth its own focused pass and test fixture with a deliberately wrong claim.
6. **Q&A**: `agent_tools.py`, `create_react_agent` wiring, REPL.
7. **Polish**: `doctor` diagnostics, packaging for PyPI, README/quickstart.

## Testing / Verification Plan

- Unit tests per node with a fake chat model (`FakeListChatModel` or a test-mode flag in `provider_factory`) — no real API calls.
- Tool unit tests: `fs_walk` against `.gitignore` fixtures; one fixture manifest per ecosystem for `manifest_parsers`; AST parsers against small known-import snippets.
- Integration test: a small multi-language fixture repo (`tests/integration/fixtures/sample_repo/`) with one deliberately misleading docstring, to assert the verifier actually catches a false claim. Run the compiled graph with scripted LLM responses; assert output files and verification report match expectations.
- DB tests via `mongomock`/`mongomock-motor` (fast, no Docker) plus a `@pytest.mark.docker` suite against a real container.
- CLI wiring tests via Typer's `CliRunner`.
- Manual end-to-end smoke test: run `code-atlas index` against a real small open-source repo, eyeball generated docs for accuracy, ask 2-3 questions in the REPL, confirm cited files/lines actually exist and say what's claimed.

### Critical files to get right first
- `src/code_atlas/orchestration/graph.py` — pipeline topology and retry contract.
- `src/code_atlas/orchestration/nodes/verifier.py` — the core differentiator.
- `src/code_atlas/db/repository.py` — the DB seam everything else depends on.
- `src/code_atlas/writers/claude_md.py` (+ base template) — worth prototyping early against a real repo to judge output quality.
- `src/code_atlas/infra/docker_manager.py` — first-run correctness gates whether the CLI works at all on a fresh machine.
