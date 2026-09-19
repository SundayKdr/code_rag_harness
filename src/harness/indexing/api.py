from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request

from harness.common.config import get_settings
from harness.common.repository import RepositoryInfo
from harness.common.repository_store import RepositoryStore
from harness.common.revision import RevisionInfo
from harness.common.revision_store import RevisionStore
from harness.indexing.models import (
    IndexingHealthResponse,
    RepositoryRegisterRequest,
    RevisionCreateRequest,
)
from harness.indexing.repository_manager import RepositoryManager
from harness.indexing.revision_manager import RevisionManager
from harness.indexing.materialization_manager import (
    MaterializationManager,
)

@asynccontextmanager
async def lifespan(
    app: FastAPI,
) -> AsyncIterator[None]:

    settings = get_settings()

    repository_store = RepositoryStore(
        settings.repository_registry_path,
    )
    revision_store = RevisionStore(
        settings.revision_registry_path,
    )

    repository_manager = RepositoryManager(
        settings=settings,
        store=repository_store,
    )
    revision_manager = RevisionManager(
        settings=settings,
        repository_store=repository_store,
        revision_store=revision_store,
    )
    materialization_manager = MaterializationManager(
        settings=settings,
        repository_store=repository_store,
        revision_store=revision_store,
    )

    app.state.materialization_manager = (
        materialization_manager
    )

    app.state.settings = settings
    app.state.repository_store = repository_store
    app.state.revision_store = revision_store
    app.state.repository_manager = repository_manager
    app.state.revision_manager = revision_manager

    yield


app = FastAPI(
    title="Code RAG Indexing API",
    version="0.2.0",
    lifespan=lifespan,
)

@app.get(
    "/health",
    response_model=IndexingHealthResponse,
)
async def health() -> IndexingHealthResponse:

    return IndexingHealthResponse(
        status="ok",
    )


@app.post(
    "/v1/repositories",
    response_model=RepositoryInfo,
)
async def register_repository(
    payload: RepositoryRegisterRequest,
    request: Request,
) -> RepositoryInfo:

    manager: RepositoryManager = (
        request.app.state.repository_manager
    )

    try:
        return await manager.register(
            payload.source
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@app.get(
    "/v1/repositories/{repository_id}",
    response_model=RepositoryInfo,
)
async def get_repository(
    repository_id: str,
    request: Request,
) -> RepositoryInfo:

    store: RepositoryStore = (
        request.app.state.repository_store
    )

    repository = store.get(repository_id)

    if repository is None:
        raise HTTPException(
            status_code=404,
            detail="Repository not found",
        )

    return repository


@app.get(
    "/v1/repositories",
    response_model=list[RepositoryInfo],
)

@app.post(
    "/v1/repositories/{repository_id}/revisions",
    response_model=RevisionInfo,
)
async def create_revision(
    repository_id: str,
    payload: RevisionCreateRequest,
    request: Request,
) -> RevisionInfo:

    manager: RevisionManager = (
        request.app.state.revision_manager
    )

    try:
        return await manager.create(
            repository_id,
            payload.ref,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@app.get(
    "/v1/revisions/{revision_id}",
    response_model=RevisionInfo,
)
async def get_revision(
    revision_id: str,
    request: Request,
) -> RevisionInfo:

    revision_store: RevisionStore = (
        request.app.state.revision_store
    )

    revision = revision_store.get(
        revision_id
    )

    if revision is None:
        raise HTTPException(
            status_code=404,
            detail="Revision not found",
        )

    return revision


async def list_repositories(
    request: Request,
) -> list[RepositoryInfo]:

    store: RepositoryStore = (
        request.app.state.repository_store
    )

    return store.list()


@app.post(
    "/v1/revisions/{revision_id}/materialize",
    response_model=RevisionInfo,
)
async def materialize_revision(
    revision_id: str,
    request: Request,
) -> RevisionInfo:

    manager: MaterializationManager = (
        request.app.state.materialization_manager
    )

    try:
        return await manager.materialize(
            revision_id
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc
