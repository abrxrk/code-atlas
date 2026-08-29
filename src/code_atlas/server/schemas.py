from pydantic import BaseModel, Field


class IndexRequest(BaseModel):
    repo_root: str


class IndexSummary(BaseModel):
    file_count: int
    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    entry_point_count: int
    module_edge_count: int
    output_paths: list[str] = Field(default_factory=list)


class IndexResponse(BaseModel):
    session_id: str
    summary: IndexSummary


class IndexProgressEvent(BaseModel):
    """One SSE event from POST /index while the pipeline is still running."""

    stage: str
    retry_count: int = 0


class IndexCompleteEvent(BaseModel):
    stage: str = "complete"
    result: IndexResponse


class IndexErrorEvent(BaseModel):
    stage: str = "error"
    message: str


class QARequest(BaseModel):
    repo_root: str
    question: str


class QAResponse(BaseModel):
    answer: str
