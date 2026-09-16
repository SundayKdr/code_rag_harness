from contextlib import asynccontextmanager
from typing import AsyncIterator
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request

from harness.clients.llm import LlmClient
from harness.common.config import get_settings
from harness.common.repository_store import (
    RepositoryStore,
)
from harness.query.graph.build import build_graph
from harness.query.models import (
    AskRequest,
    AskResponse,
    HealthResponse,
    QueryPlan,
    TokenUsage,
)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    llm = LlmClient(settings)
    repository_store = RepositoryStore(
        settings.repository_registry_path,
    )
    revision_store = RevisionStore(
        settings.revision_registry_path,
    )
    app.state.revision_store = revision_store
    graph = build_graph(llm)

    app.state.settings = settings
    app.state.llm = llm
    app.state.repository_store = repository_store
    app.state.graph = graph

    yield

    await llm.close()


app = FastAPI(
    title="Code RAG Harness",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    llm: LlmClient = request.app.state.llm
    settings = request.app.state.settings

    llm_ok = await llm.health()

    return HealthResponse(
        status="ok" if llm_ok else "degraded",
        llm_status="ok" if llm_ok else "unavailable",
        llm_model=settings.llm_model,
        )

@app.get(
    "/v1/repositories/{repository_id}/revisions",
    response_model=list[RevisionInfo],
)
async def list_query_revisions(
    repository_id: str,
    request: Request,
) -> list[RevisionInfo]:

    store: RevisionStore = (
        request.app.state.revision_store
    )

    return [
        revision
        for revision in store.list(
            repository_id=repository_id
        )
        if revision.status == RevisionStatus.READY
    ]


@app.post("/v1/ask", response_model=AskResponse)
async def ask(payload: AskRequest, request: Request) -> AskResponse:
    request_id = str(uuid4())
       
    revision_store: RevisionStore = (
        request.app.state.revision_store
    )

    revision = revision_store.get(
        payload.revision_id
    )

    if revision is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Revision not found: "
                f"{payload.revision_id}"
            ),
        )

    graph = request.app.state.graph
    try:
	result = await graph.ainvoke(
	    {
	        "request_id": request_id,
	        "revision_id": revision.revision_id,
	        "repository_id": revision.repository_id,
	        "commit_sha": revision.commit_sha,
	        "question": payload.question,
	    }
	)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Luery pipeline failed: {exc}",
        ) from exc

	return AskResponse(
	    request_id=request_id,
	    revision_id=payload.revision_id,
	    answer=result["answer"],
	    query_plan=QueryPlan.model_validate(
	        result["query_plan"]
	    ),
	    usage=TokenUsage(
	        prompt_tokens=result.get(
	            "prompt_tokens", 0
	        ),
	        completion_tokens=result.get(
	            "completion_tokens", 0
	        ),
	        total_tokens=result.get(
	            "total_tokens", 0
	        ),
	    ),
	)
