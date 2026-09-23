from datetime import datetime, timezone
from pathlib import Path
import shutil

from harness.common.config import Settings
from harness.common.repository import RepositoryInfo
from harness.common.repository_store import RepositoryStore
from harness.common.revision import (
    RevisionInfo,
    RevisionStatus,
)
from harness.common.revision_store import RevisionStore
from harness.indexing.git import GitError, run_git


class MaterializationManager:
    def __init__(
        self,
        settings: Settings,
        repository_store: RepositoryStore,
        revision_store: RevisionStore,
    ) -> None:

        self._settings = settings
        self._repository_store = repository_store
        self._revision_store = revision_store

    async def materialize(
        self,
        revision_id: str,
    ) -> RevisionInfo:

        revision = self._revision_store.get(
            revision_id
        )

        if revision is None:
            raise ValueError(
                f"Revision not found: {revision_id}"
            )

        repository = self._repository_store.get(
            revision.repository_id
        )

        if repository is None:
            raise ValueError(
                f"Repository not found: "
                f"{revision.repository_id}"
            )

        if (
            revision.status
            in {
                RevisionStatus.MATERIALIZED,
                RevisionStatus.INDEXING,
                RevisionStatus.READY,
            }
            and revision.materialized_path
        ):
            path = Path(
                revision.materialized_path
            )

            if path.exists():
                return revision

        revision.status = (
            RevisionStatus.MATERIALIZING
        )
        revision.error = None

        self._revision_store.put(revision)

        try:
            path = await self._materialize(
                repository,
                revision,
            )

            revision.materialized_path = str(path)
            revision.materialized_at = datetime.now(
                timezone.utc
            )

            revision.status = (
                RevisionStatus.MATERIALIZED
            )

            self._revision_store.put(revision)

            return revision

        except Exception as exc:
            revision.status = RevisionStatus.FAILED
            revision.error = str(exc)

            self._revision_store.put(revision)

            raise

    async def _materialize(
        self,
        repository: RepositoryInfo,
        revision: RevisionInfo,
    ) -> Path:

        mirror_path = (
            self._settings.repository_mirror_root
            / f"{repository.repository_id}.git"
        )

        materialized_path = (
            self._settings.revision_materialization_root
            / revision.revision_id
        )

        mirror_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        materialized_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        await self._ensure_mirror(
            repository,
            mirror_path,
        )

        await self._ensure_commit(
            mirror_path,
            revision.commit_sha,
        )

        if materialized_path.exists():
            shutil.rmtree(materialized_path)

        await run_git(
            "--git-dir",
            str(mirror_path),
            "worktree",
            "prune",
        )

        await run_git(
            "--git-dir",
            str(mirror_path),
            "worktree",
            "add",
            "--detach",
            str(materialized_path),
            revision.commit_sha,
        )

        resolved = await run_git(
            "rev-parse",
            "HEAD",
            cwd=materialized_path,
        )

        if resolved != revision.commit_sha:
            raise RuntimeError(
                "Materialized commit mismatch: "
                f"expected={revision.commit_sha}, "
                f"actual={resolved}"
            )

        return materialized_path


    async def _ensure_mirror(
        self,
        repository: RepositoryInfo,
        mirror_path: Path,
    ) -> None:

        if not mirror_path.exists():
            await self._create_mirror(
                repository,
                mirror_path,
            )

            return

        await self._update_mirror(
            repository,
            mirror_path,
        )


    async def _create_mirror(
        self,
        repository: RepositoryInfo,
        mirror_path: Path,
    ) -> None:

        source = self._repository_source(
            repository
        )

        await run_git(
            "clone",
            "--mirror",
            source,
            str(mirror_path),
        )

    async def _update_mirror(
        self,
        repository: RepositoryInfo,
        mirror_path: Path,
    ) -> None:

        source = self._repository_source(
            repository
        )

        await run_git(
            "--git-dir",
            str(mirror_path),
            "remote",
            "set-url",
            "origin",
            source,
        )

        await run_git(
            "--git-dir",
            str(mirror_path),
            "fetch",
            "--prune",
            "--tags",
            "origin",
            "+refs/heads/*:refs/heads/*",
        )


    @staticmethod
    def _repository_source(
        repository: RepositoryInfo,
    ) -> str:

        if repository.source_type == "local":
            if repository.local_path is None:
                raise ValueError(
                    "Local repository has no local_path"
                )

            return repository.local_path

        if repository.source_type == "git":
            if repository.remote_url is None:
                raise ValueError(
                    "Git repository has no remote_url"
                )

            return repository.remote_url

        raise ValueError(
            f"Unsupported repository type: "
            f"{repository.source_type}"
        )

    async def _ensure_commit(self, mirror_path: Path, commit_sha: str) -> None:
        if await self._commit_exists(
            mirror_path,
            commit_sha,
        ):return

        try:
            await run_git(
                "--git-dir",
                str(mirror_path),
                "fetch",
                "origin",
                commit_sha,
            )
        except GitError:
            pass

        if not await self._commit_exists(
            mirror_path,
            commit_sha,
        ):
            raise ValueError(
                f"Commit {commit_sha} is not available "
                f"in repository"
            )

    
    async def _commit_exists(self, mirror_path: Path, commit_sha: str,) -> bool:
        try:
            await run_git(
                "--git-dir",
                str(mirror_path),
                "cat-file",
                "-e",
                f"{commit_sha}^{{commit}}",
            )

            return True

        except GitError:
            return False

    
