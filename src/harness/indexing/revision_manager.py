import asyncio
from pathlib import Path
from uuid import uuid4

from harness.common.config import Settings
from harness.common.repository import RepositoryInfo
from harness.common.repository_store import RepositoryStore
from harness.common.revision import (
    RevisionInfo,
    RevisionStatus,
)
from harness.common.revision_store import RevisionStore


class RevisionManager:
    def __init__(
        self,
        settings: Settings,
        repository_store: RepositoryStore,
        revision_store: RevisionStore,
    ) -> None:

        self._settings = settings
        self._repository_store = repository_store
        self._revision_store = revision_store

    async def create(
        self,
        repository_id: str,
        ref: str,
    ) -> RevisionInfo:

        repository = self._repository_store.get(
            repository_id
        )

        if repository is None:
            raise ValueError(
                f"Repository not found: {repository_id}"
            )

        commit_sha = await self._resolve_ref(
            repository,
            ref,
        )

        existing = self._revision_store.find_by_commit(
            repository_id,
            commit_sha,
        )

        if existing is not None:
            return existing

        revision = RevisionInfo(
            revision_id=str(uuid4()),
            repository_id=repository_id,
            requested_ref=ref,
            commit_sha=commit_sha,
            status=RevisionStatus.REGISTERED,
        )

        self._revision_store.put(revision)

        return revision

    async def _resolve_ref(
        self,
        repository: RepositoryInfo,
        ref: str,
    ) -> str:

        if repository.source_type == "local":
            return await self._resolve_local_ref(
                repository,
                ref,
            )

        if repository.source_type == "git":
            return await self._resolve_remote_ref(
                repository,
                ref,
            )

        raise ValueError(
            f"Unsupported source type: "
            f"{repository.source_type}"
        )

    async def _resolve_local_ref(
        self,
        repository: RepositoryInfo,
        ref: str,
    ) -> str:

        if repository.local_path is None:
            raise ValueError(
                "Local repository has no local_path"
            )

        path = Path(repository.local_path)

        return await self._git_rev_parse(
            path,
            f"{ref}^{{commit}}",
        )

    async def _resolve_remote_ref(
        self,
        repository: RepositoryInfo,
        ref: str,
    ) -> str:

        if repository.remote_url is None:
            raise ValueError(
                "Git repository has no remote_url"
            )

        proc = await asyncio.create_subprocess_exec(
            "git",
            "ls-remote",
            repository.remote_url,
            ref,
            f"refs/heads/{ref}",
            f"refs/tags/{ref}",
            f"refs/tags/{ref}^{{}}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise ValueError(
                f"git ls-remote failed: "
                f"{stderr.decode().strip()}"
            )

        lines = [
            line
            for line in stdout.decode().splitlines()
            if line.strip()
        ]

        if not lines:
            # ref может быть непосредственно SHA.
            if self._looks_like_sha(ref):
                return ref.lower()

            raise ValueError(
                f"Cannot resolve ref: {ref}"
            )

        # Для annotated tag предпочитаем peeled ^{} SHA.
        for line in lines:
            sha, name = line.split(maxsplit=1)

            if name.endswith("^{}"):
                return sha

        sha, _ = lines[0].split(maxsplit=1)

        return sha

    async def _git_rev_parse(
        self,
        path: Path,
        ref: str,
    ) -> str:

        proc = await asyncio.create_subprocess_exec(
            "git",
            "-C",
            str(path),
            "rev-parse",
            "--verify",
            ref,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise ValueError(
                f"Cannot resolve ref {ref}: "
                f"{stderr.decode().strip()}"
            )

        return stdout.decode().strip()

    @staticmethod
    def _looks_like_sha(value: str) -> bool:
        if not 7 <= len(value) <= 40:
            return False

        return all(
            ch in "0123456789abcdefABCDEF"
            for ch in value
        )
