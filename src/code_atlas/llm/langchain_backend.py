from __future__ import annotations

from code_atlas.config.settings import RoleConfig
from code_atlas.llm.agent_backend import AgentResult


class LangChainBackend:
    def __init__(self, model) -> None:
        self._model = model

    @classmethod
    def from_role_config(cls, role_config: RoleConfig) -> "LangChainBackend":
        if role_config.provider == "anthropic":
            from langchain_anthropic import ChatAnthropic

            model = ChatAnthropic(model=role_config.model, api_key=role_config.api_key)
        elif role_config.provider == "openai":
            try:
                from langchain_openai import ChatOpenAI
            except ImportError as exc:
                raise RuntimeError(
                    "The openai provider requires the 'openai' extra. "
                    "Install it with `pip install code-atlas[openai]`."
                ) from exc

            model = ChatOpenAI(model=role_config.model, api_key=role_config.api_key)
        elif role_config.provider == "bedrock":
            try:
                from langchain_aws import ChatBedrock
            except ImportError as exc:
                raise RuntimeError(
                    "The bedrock provider requires the 'bedrock' extra. "
                    "Install it with `pip install code-atlas[bedrock]`."
                ) from exc

            model = ChatBedrock(
                model_id=role_config.model,
                region_name=role_config.region,
                credentials_profile_name=role_config.profile,
            )
        else:
            raise RuntimeError(f"LangChainBackend does not support provider '{role_config.provider}'.")

        return cls(model)

    def run(self, prompt: str, *, tools: list[str] | None = None) -> AgentResult:
        try:
            response = self._model.invoke(prompt)
        except Exception as exc:
            raise RuntimeError(f"LangChain model call failed: {exc}") from exc

        content = response.content
        text = content if isinstance(content, str) else str(content)
        return AgentResult(text=text)
