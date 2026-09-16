from typing import Annotated, Literal

from pydantic import BaseModel, Field


class LocalRepositorySource(BaseModel):
    type: Literal["local"]
    path: str


class GitRepositorySource(BaseModel):
    type: Literal["git"]
    url: str


RepositorySource = Annotated[
    LocalRepositorySource | GitRepositorySource,
    Field(discriminator="type"),
]


class RepositoryInfo(BaseModel):
    repository_id: str
    name: str

    source_type: Literal["local", "git"]

    local_path: str | None = None
    remote_url: str | None = None
