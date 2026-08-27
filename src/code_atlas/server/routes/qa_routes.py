from fastapi import APIRouter

from code_atlas.orchestration import qa_graph
from code_atlas.server.schemas import QARequest, QAResponse

router = APIRouter()


@router.post("/ask")
def ask(request: QARequest) -> QAResponse:
    answer = qa_graph.answer_question(request.repo_root, request.question)
    return QAResponse(answer=answer)
