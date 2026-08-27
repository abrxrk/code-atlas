import json
from pathlib import Path

from code_atlas.store.models import QAHistoryEntry, SessionState, VerificationClaim

_STATE_DIRNAME = ".code-atlas/state"


def save_session(repo_root: Path, state: SessionState) -> Path:
    state_dir = _state_dir(repo_root)
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "session.json"
    path.write_text(state.model_dump_json(indent=2))
    return path


def save_verification_claims(repo_root: Path, claims: list[VerificationClaim]) -> Path:
    state_dir = _state_dir(repo_root)
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "verification-claims.json"
    path.write_text(json.dumps([claim.model_dump() for claim in claims], indent=2))
    return path


def append_qa_history(repo_root: Path, entry: QAHistoryEntry) -> Path:
    state_dir = _state_dir(repo_root)
    state_dir.mkdir(parents=True, exist_ok=True)
    path = state_dir / "qa_history.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(entry.model_dump_json() + "\n")
    return path


def load_session(repo_root: Path) -> SessionState | None:
    path = _state_dir(repo_root) / "session.json"
    if not path.exists():
        return None
    return SessionState.model_validate_json(path.read_text())


def _state_dir(repo_root: Path) -> Path:
    return repo_root / _STATE_DIRNAME
