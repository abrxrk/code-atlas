from pydantic import BaseModel, Field


class SessionState(BaseModel):
    repo_root: str
    indexed_at: str  # ISO 8601, stamped by the caller — this module stays a pure I/O seam
    file_count: int
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
