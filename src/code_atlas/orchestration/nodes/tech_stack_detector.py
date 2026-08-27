from dataclasses import dataclass, field

from code_atlas.llm.provider_factory import ProviderNotConfiguredError, get_chat_model
from code_atlas.orchestration.nodes.repo_mapper import RepoMapResult

_ECOSYSTEM_LANGUAGE = {
    "npm": "JavaScript/TypeScript",
    "python": "Python",
    "go": "Go",
    "rust": "Rust",
    "java": "Java",
    "ruby": "Ruby",
    "php": "PHP",
}

_BUILD_TOOL_BY_ECOSYSTEM = {
    "npm": "npm",
    "python": "pip",
    "go": "go",
    "rust": "cargo",
    "java": "maven",
    "ruby": "bundler",
    "php": "composer",
}

_FRAMEWORK_HINTS = {
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",
    "typer": "Typer",
    "langchain": "LangChain",
    "langgraph": "LangGraph",
    "react": "React",
    "next": "Next.js",
    "vue": "Vue",
    "svelte": "Svelte",
    "express": "Express",
    "@nestjs/core": "NestJS",
}


@dataclass
class TechStack:
    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    build_tools: list[str] = field(default_factory=list)
    run_commands: list[str] = field(default_factory=list)
    notes: str | None = None  # set only when LLM disambiguation ran (or was skipped)


def run(repo_map: RepoMapResult) -> TechStack:
    ecosystems = sorted({m.ecosystem for m in repo_map.manifests})
    languages = [_ECOSYSTEM_LANGUAGE[eco] for eco in ecosystems if eco in _ECOSYSTEM_LANGUAGE]
    build_tools = [_BUILD_TOOL_BY_ECOSYSTEM[eco] for eco in ecosystems if eco in _BUILD_TOOL_BY_ECOSYSTEM]

    all_deps = {dep.lower() for m in repo_map.manifests for dep in m.dependencies}
    frameworks = sorted({name for key, name in _FRAMEWORK_HINTS.items() if key in all_deps})

    run_commands = [f"{key}: {cmd}" for m in repo_map.manifests for key, cmd in m.scripts.items()]

    notes = _disambiguate(ecosystems, repo_map) if len(ecosystems) > 1 else None

    return TechStack(
        languages=languages,
        frameworks=frameworks,
        build_tools=build_tools,
        run_commands=run_commands,
        notes=notes,
    )


def _disambiguate(ecosystems: list[str], repo_map: RepoMapResult) -> str:
    """One LLM call, only reached when multiple ecosystems were detected."""
    try:
        model = get_chat_model("analysis")
    except ProviderNotConfiguredError:
        return (
            f"Multiple ecosystems detected ({', '.join(ecosystems)}) — LLM disambiguation "
            "skipped, no provider configured yet. Run `code-atlas config` to enable it."
        )

    manifest_list = "\n".join(f"- {m.manifest_path} ({m.ecosystem})" for m in repo_map.manifests)
    prompt = (
        "This repo has manifests from multiple ecosystems. Given this list, say in one "
        "short sentence which is the primary language/stack, or if it's genuinely a "
        f"polyglot monorepo:\n\n{manifest_list}"
    )
    response = model.invoke(prompt)
    return response.content if isinstance(response.content, str) else str(response.content)
