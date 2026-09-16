import json
import os
from pathlib import Path

from harness.common.revision import RevisionInfo


class RevisionStore:
    def __init__(self, registry_path: Path) -> None:
        self._path = registry_path

        self._path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def get(
        self,
        revision_id: str,
    ) -> RevisionInfo | None:

        revisions = self._load()

        raw = revisions.get(revision_id)

        if raw is None:
            return None

        return RevisionInfo.model_validate(raw)

    def list(
        self,
        *,
        repository_id: str | None = None,
    ) -> list[RevisionInfo]:

        result = [
            RevisionInfo.model_validate(value)
            for value in self._load().values()
        ]

        if repository_id is not None:
            result = [
                item
                for item in result
                if item.repository_id == repository_id
            ]

        return result

    def find_by_commit(
        self,
        repository_id: str,
        commit_sha: str,
    ) -> RevisionInfo | None:

        for revision in self.list(
            repository_id=repository_id,
        ):
            if revision.commit_sha == commit_sha:
                return revision

        return None

    def put(
        self,
        revision: RevisionInfo,
    ) -> None:

        revisions = self._load()

        revisions[revision.revision_id] = (
            revision.model_dump(mode="json")
        )

        self._store(revisions)

    def _load(self) -> dict[str, dict]:
        if not self._path.exists():
            return {}

        with self._path.open(
            "r",
            encoding="utf-8",
        ) as f:
            data = json.load(f)

        if not isinstance(data, dict):
            raise RuntimeError(
                f"Invalid revision registry: {self._path}"
            )

        return data

    def _store(
        self,
        revisions: dict[str, dict],
    ) -> None:

        tmp = self._path.with_suffix(
            self._path.suffix + ".tmp"
        )

        with tmp.open(
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                revisions,
                f,
                ensure_ascii=False,
                indent=2,
            )
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp, self._path)
