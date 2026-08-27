from pydantic import BaseModel, Field


class SessionState(BaseModel):
    repo_root: str
    indexed_at: str  # ISO 8601, stamped by the caller — this module stays a pure I/O seam
    file_count: int
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)


class VerificationClaim(BaseModel):
    """One row of the verification-claims.json audit trail."""

    claim_type: str  # "entry_point" | "module_edge"
    description: str
    verified: bool
    reason: str


class QAHistoryEntry(BaseModel):
    """One row of the qa_history.jsonl log — one line per `ask` call."""

    question: str
    answer: str
    asked_at: str  # ISO 8601, stamped by the caller — this module stays a pure I/O seam
