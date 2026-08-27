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


class QARequest(BaseModel):
    repo_root: str
    question: str


class QAResponse(BaseModel):
    answer: str
