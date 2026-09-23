import json
import os
from pathlib import Path

from harness.common.repository import RepositoryInfo


class RepositoryStore:
    def __init__(self, registry_path: Path) -> None:
        self._path = registry_path

        self._path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def get(
        self,
        repository_id: str,
    ) -> RepositoryInfo | None:

        repositories = self._load()

        raw = repositories.get(repository_id)

        if raw is None:
            return None

        return RepositoryInfo.model_validate(raw)

    def list(self) -> list[RepositoryInfo]:
        return [
            RepositoryInfo.model_validate(value)
            for value in self._load().values()
        ]

    def put(
        self,
        repository: RepositoryInfo,
    ) -> RepositoryInfo:

        repositories = self._load()

        existing_rep = next((existing_rep for existing_rep in repositories.values() if existing_rep["remote_url"] == repository.remote_url), None,)

        if existing_rep:
            return RepositoryInfo.model_validate(existing_rep)
        
        repositories[repository.repository_id] = (
            repository.model_dump(mode="json")
        )

        self._store(repositories)
        return repositories[repository.repository_id]

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
                f"Invalid repository registry: {self._path}"
            )

        return data

    def _store(
        self,
        repositories: dict[str, dict],
    ) -> None:

        tmp = self._path.with_suffix(
            self._path.suffix + ".tmp"
        )

        with tmp.open(
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                repositories,
                f,
                ensure_ascii=False,
                indent=2,
            )
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp, self._path)
        return data

    def _store(
        self,
        repositories: dict[str, dict],
    ) -> None:

        tmp = self._path.with_suffix(
            self._path.suffix + ".tmp"
        )

        with tmp.open(
            "w",
            encoding="utf-8",
        ) as f:
            json.dump(
                repositories,
                f,
                ensure_ascii=False,
                indent=2,
            )
            f.flush()
            os.fsync(f.fileno())

        os.replace(tmp, self._path)
