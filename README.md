# code-atlas

A terminal tool that maps a codebase deeply and **verifiably** — tech stack, entry points, module relationships — writing the result out as `CLAUDE.md`, `AGENTS.md`, and a `.code-atlas/` doc set that other coding agents can read. Also gives you a terminal Q&A interface to ask questions about the codebase directly.

Every claim it makes (an entry point, a module's purpose, a dependency edge) is re-checked against the actual source before being written out. Claims that can't be verified are marked as such, not silently kept or dropped — that's the difference from a shallow `/init`-style summary.

Status: early — Phase 1 (CLI skeleton, config, `doctor`) is done; indexing/Q&A aren't wired up yet.

## Prerequisites

- Python 3.11+
- An API key for at least one LLM provider (Anthropic and/or OpenAI)

## Install

```bash
uvx code-atlas       # ephemeral, npx-equivalent
# or
pipx install code-atlas   # persistent
```

## Usage

```bash
code-atlas index [path]      # index a repo (defaults to cwd), drops into a Q&A REPL when done
code-atlas ask "question"    # one-shot question against an existing index
code-atlas serve             # run the local server in the foreground, for debugging
code-atlas doctor            # check config/environment health
code-atlas config            # configure LLM provider + API key
```

First run prompts for provider + API key and writes `~/.code-atlas/config.toml`.

## Architecture

CLI (Typer) → local FastAPI server → LangGraph orchestration → JSON-file persistence (`.code-atlas/state/`) + outbound LLM calls, all running on your own machine. No hosted backend, no accounts.
