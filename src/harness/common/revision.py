from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field


class RevisionStatus(StrEnum):
    REGISTERED = "registered"
    INDEXING = "indexing"
    READY = "ready"
    FAILED = "failed"


class RevisionInfo(BaseModel):
    revision_id: str
    repository_id: str

    requested_ref: str
    commit_sha: str

    status: RevisionStatus

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    indexed_at: datetime | None = None

    chunk_count: int = 0

    error: str | None = None
