import shutil

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.shortcuts import confirm as pt_confirm

from code_atlas.cli.ui import ACCENT, MUTED, console, print_error, print_info, print_pending, print_success
from code_atlas.config.settings import ROLES, ProviderName, RoleConfig, Settings, save_settings

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
    """Interactively collect one provider and apply it to every role.

    One-time linear flow (not a persistent REPL). Uses prompt_toolkit's
    one-off prompt()/confirm() rather than typer/click prompts — this
    wizard can be triggered from inside the REPL, which has already put
    the terminal into prompt_toolkit's own raw input mode; mixing in
    click's cooked-mode-expecting input() there caused literal control
    characters (^C) to leak into the terminal instead of being handled.
    """
    console.print()
    console.print(f"[bold {ACCENT}]Welcome to code-atlas — let's set up your LLM provider.[/bold {ACCENT}]")
    console.print(f"[{MUTED}]This one provider is used for everything: {', '.join(ROLES)}.[/{MUTED}]")
    console.print()

    role_config = _configure_provider()
    settings = Settings(**dict.fromkeys(ROLES, role_config))
    save_settings(settings)

    console.print()
    model_note = f" ({role_config.model})" if role_config.model else ""
    print_success(f"Setup complete — using {_PROVIDER_LABELS[role_config.provider]}{model_note} for everything.")

    return settings


def _prompt(message: str, *, default: str = "", password: bool = False) -> str:
    """Like click's prompt(default=...): show `[default]` as a hint and fall
    back to it on empty input — never pre-fill prompt_toolkit's edit buffer
    with literal editable text, which makes typing over it append instead
    of replace (e.g. a shown "2" plus a typed "2" becomes "22")."""
    hint = f" [{default}]" if default else ""
    response = pt_prompt(f"{message}{hint}: ", is_password=password).strip()
    return response or default


def _configure_provider() -> RoleConfig:
    provider = _ask_provider()

    if provider in ("anthropic", "openai"):
        api_key = _prompt(f"  {_PROVIDER_LABELS[provider]} — API key", password=True)
        model = _prompt("  Model name", default=_default_model(provider))
        return RoleConfig(provider=provider, api_key=api_key, model=model)

    if provider == "claude-code":
        if shutil.which("claude") is None:
            print_error("Could not find `claude` on your PATH. Install Claude Code and log in before indexing.")
        else:
            print_pending("Found `claude` on PATH — assuming you're already logged in.")
        model = None
        if pt_confirm("  Override the default model?"):
            model = _prompt("  Model name")
        return RoleConfig(provider=provider, model=model)

    region = _prompt("  AWS region", default="us-east-1")
    profile = _prompt("  AWS profile (optional, blank for default)")
    model = _prompt("  Model id", default="anthropic.claude-3-5-sonnet-20241022-v2:0")
    return RoleConfig(provider=provider, region=region, profile=profile or None, model=model)


def _ask_provider() -> ProviderName:
    print_info("Choose a provider:")
    for key, provider in _PROVIDER_CHOICES.items():
        console.print(f"    [{ACCENT}]{key}[/{ACCENT}]) {_PROVIDER_LABELS[provider]}")

    choice = _prompt("  Provider", default="2")
    while choice not in _PROVIDER_CHOICES:
        console.print(f"[{MUTED}]Please enter one of: {', '.join(_PROVIDER_CHOICES)}[/{MUTED}]")
        choice = _prompt("  Provider", default="2")
    return _PROVIDER_CHOICES[choice]


def _default_model(provider: ProviderName) -> str:
    return "claude-sonnet-4-5" if provider == "anthropic" else "gpt-5"
