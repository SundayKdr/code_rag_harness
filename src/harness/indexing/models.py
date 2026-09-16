from pydantic import BaseModel, Field

from harness.common.repository import RepositorySource


class RepositoryRegisterRequest(BaseModel):
    source: RepositorySource


class RevisionCreateRequest(BaseModel):
    ref: str = Field(
        min_length=1,
        max_length=512,
    )


class IndexingHealthResponse(BaseModel):
    status: str
