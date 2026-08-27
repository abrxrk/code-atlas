from code_atlas.config.settings import Role, load_settings
from code_atlas.llm.agent_backend import AgentBackend


class ProviderNotConfiguredError(RuntimeError):
    def __init__(self, role: str) -> None:
        super().__init__(f"No provider configured for role '{role}'. Run `code-atlas config` first.")
        self.role = role


def get_agent_backend(role: Role) -> AgentBackend:
    settings = load_settings()
    role_config = getattr(settings, role)
    if role_config is None:
        raise ProviderNotConfiguredError(role)

    if role_config.provider == "claude-code":
        from code_atlas.llm.claude_code_backend import ClaudeCodeBackend

        return ClaudeCodeBackend(model=role_config.model)

    from code_atlas.llm.langchain_backend import LangChainBackend

    return LangChainBackend.from_role_config(role_config)
