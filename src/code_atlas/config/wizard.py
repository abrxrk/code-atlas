import shutil

import typer

from code_atlas.cli.ui import ACCENT, MUTED, console, print_error, print_info, print_pending, print_success
from code_atlas.config.settings import ROLES, ProviderName, Role, RoleConfig, Settings, save_settings

_PROVIDER_CHOICES: dict[str, ProviderName] = {
    "1": "anthropic",
    "2": "claude-code",
    "3": "openai",
    "4": "bedrock",
}

_PROVIDER_LABELS: dict[ProviderName, str] = {
    "anthropic": "Anthropic API key",
    "claude-code": "Claude Code login",
    "openai": "OpenAI API key",
    "bedrock": "AWS Bedrock",
}


def run_setup_wizard() -> Settings:
    """Interactively collect provider config for each role and save it.

    One-time linear flow (not a persistent REPL), so plain typer.prompt /
    typer.confirm is intentional here rather than prompt_toolkit.
    """
    console.print()
    console.print(f"[bold {ACCENT}]Welcome to code-atlas — let's set up your LLM provider(s).[/bold {ACCENT}]")
    console.print(f"[{MUTED}]You'll configure a provider for each of: {', '.join(ROLES)}.[/{MUTED}]")

    role_configs: dict[Role, RoleConfig] = {}
    for role in ROLES:
        console.print()
        console.print(f"[bold {ACCENT}]Role: {role}[/bold {ACCENT}]")
        role_configs[role] = _configure_role(role)

    settings = Settings(**role_configs)
    save_settings(settings)

    console.print()
    print_success("Setup complete — config saved.")
    for role in ROLES:
        cfg = role_configs[role]
        model_note = f" ({cfg.model})" if cfg.model else ""
        console.print(f"  [{ACCENT}]{role}:[/{ACCENT}] {_PROVIDER_LABELS[cfg.provider]}{model_note}")

    return settings


def _configure_role(role: Role) -> RoleConfig:
    provider = _ask_provider()

    if provider in ("anthropic", "openai"):
        api_key = typer.prompt(f"  {_PROVIDER_LABELS[provider]} — API key", hide_input=True)
        model = typer.prompt("  Model name", default=_default_model(provider))
        return RoleConfig(provider=provider, api_key=api_key, model=model)

    if provider == "claude-code":
        if shutil.which("claude") is None:
            print_error("Could not find `claude` on your PATH. Install Claude Code and log in before indexing.")
        else:
            print_pending("Found `claude` on PATH — assuming you're already logged in.")
        model = None
        if typer.confirm("  Override the default model?", default=False):
            model = typer.prompt("  Model name")
        return RoleConfig(provider=provider, model=model)

    region = typer.prompt("  AWS region", default="us-east-1")
    profile = typer.prompt("  AWS profile (optional, blank for default)", default="", show_default=False)
    model = typer.prompt("  Model id", default="anthropic.claude-3-5-sonnet-20241022-v2:0")
    return RoleConfig(provider=provider, region=region, profile=profile or None, model=model)


def _ask_provider() -> ProviderName:
    print_info("Choose a provider:")
    for key, provider in _PROVIDER_CHOICES.items():
        console.print(f"    [{ACCENT}]{key}[/{ACCENT}]) {_PROVIDER_LABELS[provider]}")
    choice = typer.prompt(
        "  Provider",
        default="2",
        show_choices=False,
    )
    while choice not in _PROVIDER_CHOICES:
        console.print(f"[{MUTED}]Please enter one of: {', '.join(_PROVIDER_CHOICES)}[/{MUTED}]")
        choice = typer.prompt("  Provider", default="2")
    return _PROVIDER_CHOICES[choice]


def _default_model(provider: ProviderName) -> str:
    return "claude-sonnet-4-5" if provider == "anthropic" else "gpt-5"
