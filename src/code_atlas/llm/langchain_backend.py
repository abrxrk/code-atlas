from __future__ import annotations

from code_atlas.config.settings import RoleConfig
from code_atlas.llm.agent_backend import AgentResult

_TOOL_BUILDERS = {}


def _register_tool(name):
    def decorator(func):
        _TOOL_BUILDERS[name] = func
        return func

    return decorator


@_register_tool("read_file")
def _build_read_file(repo_root: str):
    from langchain_core.tools import tool

    from code_atlas.tools.agent_tools import read_file

    @tool
    def read_file_tool(relative_path: str) -> str:
        """Read a file's contents from the repo, given a path relative to the repo root."""
        return read_file(repo_root, relative_path)

    return read_file_tool


@_register_tool("grep_repo")
def _build_grep_repo(repo_root: str):
    from langchain_core.tools import tool

    from code_atlas.tools.agent_tools import grep_repo

    @tool
    def grep_repo_tool(pattern: str) -> str:
        """Search the repo for a text pattern and return matching lines with file:line."""
        return grep_repo(repo_root, pattern)

    return grep_repo_tool


@_register_tool("list_dir")
def _build_list_dir(repo_root: str):
    from langchain_core.tools import tool

    from code_atlas.tools.agent_tools import list_dir

    @tool
    def list_dir_tool(relative_path: str = "") -> str:
        """List the entries of a directory in the repo, given a path relative to the repo root."""
        return list_dir(repo_root, relative_path)

    return list_dir_tool


@_register_tool("list_modules")
def _build_list_modules(repo_root: str):
    from langchain_core.tools import tool

    from code_atlas.tools.agent_tools import list_modules

    @tool
    def list_modules_tool() -> str:
        """List the names of all indexed module docs available for this repo."""
        return list_modules(repo_root)

    return list_modules_tool


@_register_tool("get_module_doc")
def _build_get_module_doc(repo_root: str):
    from langchain_core.tools import tool

    from code_atlas.tools.agent_tools import get_module_doc

    @tool
    def get_module_doc_tool(module_name: str) -> str:
        """Fetch the full text of an indexed module doc by module name."""
        return get_module_doc(repo_root, module_name)

    return get_module_doc_tool


class LangChainBackend:
    def __init__(self, model, repo_root: str | None = None) -> None:
        self._model = model
        self._repo_root = repo_root

    @classmethod
    def from_role_config(cls, role_config: RoleConfig, repo_root: str | None = None) -> "LangChainBackend":
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

        return cls(model, repo_root=repo_root)

    def run(self, prompt: str, *, tools: list[str] | None = None) -> AgentResult:
        if tools:
            if self._repo_root is None:
                raise RuntimeError(
                    "LangChainBackend.run() was called with tools but no repo_root was "
                    "configured; construct it via get_agent_backend(role, repo_root=...)."
                )
            return self._run_with_tools(prompt, tools)

        try:
            response = self._model.invoke(prompt)
        except Exception as exc:
            raise RuntimeError(f"LangChain model call failed: {exc}") from exc

        content = response.content
        text = content if isinstance(content, str) else str(content)
        return AgentResult(text=text)

    def _run_with_tools(self, prompt: str, tools: list[str]) -> AgentResult:
        from langgraph.prebuilt import create_react_agent

        bound_tools = []
        for name in tools:
            builder = _TOOL_BUILDERS.get(name)
            if builder is None:
                raise RuntimeError(f"Unrecognized tool name '{name}' requested for LangChainBackend.")
            bound_tools.append(builder(self._repo_root))

        try:
            agent = create_react_agent(self._model, bound_tools)
            result = agent.invoke({"messages": [("user", prompt)]})
        except Exception as exc:
            raise RuntimeError(f"LangChain tool-calling agent run failed: {exc}") from exc

        messages = result.get("messages", [])
        if not messages:
            raise RuntimeError("LangChain tool-calling agent returned no messages.")
        content = messages[-1].content
        text = content if isinstance(content, str) else str(content)
        return AgentResult(text=text)
