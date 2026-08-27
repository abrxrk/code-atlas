from langchain_core.language_models import BaseChatModel

from code_atlas.config.settings import Role, load_settings


class ProviderNotConfiguredError(RuntimeError):
    def __init__(self, role: str) -> None:
        super().__init__(f"No provider configured for role '{role}'. Run `code-atlas config` first.")
        self.role = role


def get_chat_model(role: Role) -> BaseChatModel:
    settings = load_settings()
    role_config = getattr(settings, role)
    if role_config is None:
        raise ProviderNotConfiguredError(role)

    if role_config.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=role_config.model, api_key=role_config.api_key)

    if role_config.provider == "openai":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model=role_config.model, api_key=role_config.api_key)

    if role_config.provider == "bedrock":
        from langchain_aws import ChatBedrock

        return ChatBedrock(
            model_id=role_config.model,
            region_name=role_config.region,
            credentials_profile_name=role_config.profile,
        )

    raise ValueError(f"Unknown provider: {role_config.provider}")
