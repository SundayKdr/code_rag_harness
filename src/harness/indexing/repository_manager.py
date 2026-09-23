from pathlib import Path
from uuid import uuid4

from harness.common.config import Settings
from harness.common.repository import (
    GitRepositorySource,
    LocalRepositorySource,
    RepositoryInfo,
    RepositorySource,
)
from harness.common.repository_store import RepositoryStore


class RepositoryManager:
    def __init__(
        self,
        settings: Settings,
        store: RepositoryStore,
    ) -> None:
        self._settings = settings
        self._store = store

    async def register(
        self,
        source: RepositorySource,
    ) -> RepositoryInfo:

        if isinstance(source, LocalRepositorySource):
            repository = self._register_local(source)

        elif isinstance(source, GitRepositorySource):
            repository = self._register_git(source)

        else:
            raise ValueError(
                f"Unsupported repository source: {type(source)}"
            )

        return self._store.put(repository)

    def _register_local(
        self,
        source: LocalRepositorySource,
    ) -> RepositoryInfo:

        allowed_root = (
            self._settings
            .repository_local_root
            .expanduser()
            .resolve()
        )

        path = (
            Path(source.path)
            .expanduser()
            .resolve()
        )

        if not path.is_relative_to(allowed_root):
            raise ValueError(
                f"Repository path {path} is outside "
                f"allowed root {allowed_root}"
            )

        if not path.exists():
            raise ValueError(
                f"Repository does not exist: {path}"
            )

        if not path.is_dir():
            raise ValueError(
                f"Repository is not a directory: {path}"
            )

        return RepositoryInfo(
            repository_id=str(uuid4()),
            name=path.name,
            source_type="local",
            local_path=str(path),
        )

    def _register_git(
        self,
        source: GitRepositorySource,
    ) -> RepositoryInfo:

        return RepositoryInfo(
            repository_id=str(uuid4()),
            name=self._git_repository_name(source.url),
            source_type="git",
            remote_url=source.url,
        )

    @staticmethod
    def _git_repository_name(
        url: str,
    ) -> str:

        name = url.rstrip("/").rsplit("/", 1)[-1]

        if name.endswith(".git"):
            name = name[:-4]

        return name
