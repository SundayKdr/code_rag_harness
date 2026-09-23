from __future__ import annotations

import asyncio
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


class RepositoryTreeError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class RepositoryTree:
    files: tuple[str, ...]
    prompt_view: str


async def load_repository_tree(
    revision_root: Path,
) -> RepositoryTree:

    revision_root = revision_root.resolve()

    process = await asyncio.create_subprocess_exec(
        "git",
        "-C",
        str(revision_root),
        "ls-tree",
        "-r",
        "--name-only",
        "HEAD",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise RepositoryTreeError(
            stderr.decode(
                "utf-8",
                errors="replace",
            ).strip()
        )

    files = tuple(
        sorted(
            path
            for path in stdout.decode(
                "utf-8",
                errors="strict",
            ).splitlines()
            if path
        )
    )

    return RepositoryTree(
        files=files,
        prompt_view=_build_prompt_view(files),
    )


def _build_prompt_view(
    files: tuple[str, ...],
    *,
    examples_per_directory: int = 8,
) -> str:

    files_by_directory: dict[str, list[str]] = defaultdict(list)

    for file_path in files:
        path = PurePosixPath(file_path)

        directory = str(path.parent)

        files_by_directory[directory].append(
            path.name
        )

    lines: list[str] = []

    for directory in sorted(
        files_by_directory,
        key=lambda item: (
            item.count("/"),
            item,
        ),
    ):
        names = sorted(
            files_by_directory[directory]
        )

        extensions = Counter(
            _extension(name)
            for name in names
        )

        extension_summary = ", ".join(
            f"{ext}:{count}"
            for ext, count in extensions.most_common()
        )

        examples = ", ".join(
            names[:examples_per_directory]
        )

        indent = "  " * (
            0
            if directory == "."
            else directory.count("/") + 1
        )

        display_directory = (
            "."
            if directory == "."
            else directory
        )

        lines.append(
            f"{indent}{display_directory}/ "
            f"[files={len(names)}; "
            f"extensions={extension_summary}]"
        )

        if examples:
            lines.append(
                f"{indent}  examples: {examples}"
            )

    return "\n".join(lines)


def _extension(
    filename: str,
) -> str:

    suffix = PurePosixPath(
        filename
    ).suffix.lower()

    if not suffix:
        return "<none>"

    return suffix
