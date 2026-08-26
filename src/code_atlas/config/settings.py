from typing import Literal

import tomli_w
from pydantic import BaseModel
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

from code_atlas.config.paths import CONFIG_FILE, ensure_config_dir

ProviderName = Literal["anthropic", "openai", "bedrock"]
Role = Literal["analysis", "verifier", "qa"]

ROLES: tuple[Role, ...] = ("analysis", "verifier", "qa")


class RoleConfig(BaseModel):
    provider: ProviderName
    model: str
    api_key: str | None = None
    region: str | None = None
    profile: str | None = None


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        toml_file=CONFIG_FILE,
        env_prefix="CODE_ATLAS_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    analysis: RoleConfig | None = None
    verifier: RoleConfig | None = None
    qa: RoleConfig | None = None

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings, env_settings, TomlConfigSettingsSource(settings_cls))


def config_exists() -> bool:
    return CONFIG_FILE.exists()


def load_settings() -> Settings:
    return Settings()


def save_settings(settings: Settings) -> None:
    ensure_config_dir()
    data = settings.model_dump(exclude_none=True, mode="json")
    with CONFIG_FILE.open("wb") as f:
        tomli_w.dump(data, f)
    CONFIG_FILE.chmod(0o600)
