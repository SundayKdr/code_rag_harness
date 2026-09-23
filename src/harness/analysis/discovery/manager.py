from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path
from pathlib import PurePosixPath
from collections import Counter
from collections import defaultdict
from fnmatch import fnmatchcase
from functools import lru_cache
from pathlib import PurePosixPath

from openai.types.chat import (
    ChatCompletionMessageParam,
)

from harness.analysis.discovery.models import (
    RepositoryLayoutProposal,
    RepositoryLayoutReview,
    AnalysisUnitProposal
)
from harness.analysis.discovery.tree import (
    RepositoryTree,
    load_repository_tree,
)
from harness.analysis.models import (
    AnalysisUnit,
    RepositoryLayout,
    make_analysis_unit_id,
    PatternChange,
    RepositoryLayoutPatch
)
from harness.clients.llm import LlmClient
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


_IDENTIFIER_RE = re.compile(
    r"[^a-z0-9_]+"
)

_SOURCE_EXTENSION_FAMILY: dict[str, str] = {
    ".c": "clang",
    ".cc": "clang",
    ".cpp": "clang",
    ".cxx": "clang",
    ".m": "clang",
    ".mm": "clang",
    ".cu": "clang",
    ".C" : "clang",

    ".rs": "rust",
    ".py": "python",
    ".go": "go",

    ".js": "js_ts",
    ".jsx": "js_ts",
    ".ts": "js_ts",
    ".tsx": "js_ts",

    ".java": "jvm",
    ".kt": "jvm",
    ".kts": "jvm",

    ".cs": "dotnet",

    ".pl": "perl",
    ".pm": "perl",

    ".sh": "shell",
    ".bash": "shell",

    ".cocci": "coccinelle",
}

_LANGUAGE_ALIASES = {
    "c++": "cpp",
    "cxx": "cpp",
    "c#": "csharp",
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "rs": "rust",
}


def _normalize_identifier(
    value: str,
) -> str:

    value = value.strip().lower()
    value = value.replace("+","p")
    value = value.replace("#","sharp")
    value = value.replace("-","_")
    value = _IDENTIFIER_RE.sub(
        "_",
        value,
    )
    return value.strip("_")


def _normalize_language(
    value: str,
) -> str:

    value = value.strip().lower()

    alias = _LANGUAGE_ALIASES.get(
        value
    )

    if alias is not None:
        return alias

    return _normalize_identifier(
        value
    )

def _format_validation_errors(
    *,
    uncovered: list[tuple[str, str]],
    wrong_family: list[tuple[str, str, str]],
) -> str:

    groups = defaultdict(list)

    for path, expected in uncovered:
        directory = str(PurePosixPath(path).parent)
        groups[("uncovered", expected, directory)].append(path)

    for path, actual, expected in wrong_family:
        directory = str(PurePosixPath(path).parent)
        groups[
            ("wrong_family", f"{actual}->{expected}", directory)
        ].append(path)

    lines = [
        "Correct the following repository layout errors.",
        f"Total uncovered files: {len(uncovered)}",
        f"Total wrong-family files: {len(wrong_family)}",
    ]

    for (kind, family, directory), paths in sorted(groups.items()):
        lines.append(
            f"{kind}: family={family}, directory={directory}, "
            f"count={len(paths)}, examples={paths[:5]}"
        )

    return "\n".join(lines)



class DiscoveryError(RuntimeError):
    pass


_PARTITION_SYSTEM_PROMPT = """
You analyze the directory tree of a source-code repository.

Your task is to partition tracked SOURCE CODE files by programming
language family.

Identify ONLY programming languages that are actually present in the
provided repository tree, then partition their source files.

The list of supported language families below is a list of POSSIBLE
outputs, not a checklist. Most repositories use only a subset.

This is NOT project discovery.

Do not identify build-system boundaries, modules, packages,
workspaces, or individual projects.

Identify every programming language that is actually present
in the repository.

Do NOT restrict the result to languages supported by the indexing
system. Discovery describes the repository, not analyzer capabilities.

Use a stable lowercase identifier for language_family.

For common language ecosystems, use these canonical families:

clang: c, cpp, cuda
rust: rust
python: python
go: go
js_ts: javascript, typescript
jvm: java, kotlin
dotnet: csharp

For other languages, use an appropriate lowercase family name.

Examples:
perl: perl
ruby: ruby
lua: lua
shell: shell

Only return language families that are actually present.
Do not return placeholder units with empty include_patterns.

Return glob patterns relative to repository root.

Include only source-code files useful for code intelligence.

Do not include:
- documentation
- images
- binary files
- generated build output
- ordinary configuration files merely because they exist

A repository may contain several language families.

Directories may contain files from multiple languages. In that case
use file patterns rather than assigning the whole directory blindly.

Do not invent paths that are not supported by the supplied tree.

Do not classify the same source file into multiple language families.

IMPORTANT:
Return units ONLY for language families that are actually present
in the repository.

Do NOT return placeholder units for unsupported or absent languages.

Every returned unit MUST contain at least one include pattern.

Bad:
{
  "language_family": "rust",
  "languages": ["rust"],
  "include_patterns": []
}

Return ONLY JSON matching the supplied schema.
""".strip()


_REVIEW_SYSTEM_PROMPT = """
You verify the final programming-language partition of a source repository.

Your task is ONLY to decide whether the partition is good enough
for language-specific code indexing.

Do NOT rewrite the partition.
Do NOT propose glob patterns.
Do NOT enumerate individual files.
Do NOT provide detailed explanations.

Check only for major correctness problems:

- a source-code language is missing;
- a language family is clearly wrong;
- a major source-code subtree is omitted;
- source files are assigned to an unrelated language family.

Ignore:

- minor omissions;
- stylistic improvements;
- optional refinements;
- build-system boundaries;
- project boundaries;
- package/workspace structure;
- configuration files;
- documentation;
- generated files;
- minor file-level mistakes.

Return at most 5 issues.

Each issue must be one short sentence.

Summarize repeated problems.

Bad:
"foo.py is missing, bar.py is missing, baz.py is missing"

Good:
"Python sources under tools/ are missing."

If the partition is acceptable for language-level indexing, return:

{
  "valid": true,
  "issues": []
}

The complete response must fit within 800 tokens.

Return ONLY valid JSON matching the schema.
""".strip()

_REPAIR_SYSTEM_PROMPT = """
You repair an existing repository language partition.

The deterministic validator has found concrete errors.

Return ONLY the changes required to correct these errors.

Do not regenerate the repository layout.
Do not repeat unchanged patterns.
Do not change unrelated language families.

Operations:

add_patterns:
    Include previously uncovered source files.

remove_patterns:
    Remove an incorrect existing include pattern.

add_exclusions:
    Exclude incorrectly matched files without removing
    an otherwise valid broad include pattern.

You may introduce a new language family if necessary.
For a new family, provide its languages.

Important:
- Every reported uncovered group must be addressed.
- Every reported wrong-family group must be addressed.
- Preserve all correct existing assignments.
- Use repository-relative patterns.
- Return an empty changes list only if no corrections
  are necessary.

Return ONLY valid JSON matching the supplied schema.
""".strip()

class DiscoveryManager:
    def __init__(
        self,
        llm: LlmClient,
        *,
        max_attempts: int = 3,
    ) -> None:
        self._llm = llm
        self._max_attempts = max_attempts

    async def discover(
        self,
        *,
        revision_id: str,
        revision_root: Path,
    ) -> RepositoryLayout:

        logger.info(
            "Discovery started: revision=%s",
            revision_id,
        )

        tree = await load_repository_tree(revision_root)
        proposal = await self._propose(tree=tree)

        logger.info(
            f"self._propose proposal={proposal}"
        )

        last_error = ""

        for attempt in range(1, self._max_attempts + 1):
            logger.info(
                "Discovery attempt %d/%d",
                attempt,
                self._max_attempts,
            )

            try:
                layout = self._resolve(
                    revision_id=revision_id,
                    tree=tree,
                    proposal=proposal,
                )
            except DiscoveryError as exc:
                last_error = str(exc)

                logger.warning(
                    "Layout validation failed:\n%s",
                    last_error,
                )
            else:
                review = await self._review(
                    tree=tree,
                    layout=layout,
                )

                if review.valid:
                    logger.info(
                        "Discovery completed: %d units",
                        len(layout.units),
                    )
                    return layout

                last_error = "\n".join(review.issues)

                logger.warning(
                    "Layout review failed:\n%s",
                    last_error,
                )

            # На последней попытке больше не вызываем LLM.
            if attempt == self._max_attempts:
                break

            logger.info(
                "Sending validation errors to LLM for repair"
            )

            if attempt >= self._max_attempts:
                break

            proposal = await self._repair(
                tree=tree,
                proposal=proposal,
                issue=last_error,
            )

            logger.info(
                f"self._repair proposal={proposal}"
            )
            
            continue
        
        raise DiscoveryError(
            f"Discovery failed after {self._max_attempts} "
            f"attempts. Last validation errors:\n{last_error}"
        )

    def _find_uncovered_source_files(
        tree: RepositoryTree,
        assigned_files: set[str],
    ) -> list[tuple[str, str]]:

        missing: list[tuple[str, str]] = []

        for file_path in tree.files:
            suffix = PurePosixPath(file_path).suffix.lower()

            expected_family = _SOURCE_EXTENSION_FAMILY.get(
                suffix
            )

            if expected_family is None:
                continue

            if file_path not in assigned_files:
                missing.append(
                    (
                        file_path,
                        expected_family,
                    )
                )

        return missing

    async def _propose(
        self,
        *,
        tree: RepositoryTree,
    ) -> RepositoryLayoutProposal:

        messages: list[
            ChatCompletionMessageParam
        ] = [
            {
                "role": "system",
                "content": (
                    _PARTITION_SYSTEM_PROMPT
                    + "\n\nJSON schema:\n"
                    + json.dumps(
                        RepositoryLayoutProposal
                        .model_json_schema(),
                        ensure_ascii=False,
                    )
                ),
            },
            {
                "role": "user",
                "content": (
                    "Repository tree summary:\n\n"
                    + tree.prompt_view
                ),
            },
        ]

        result = await self._llm.complete_json(
            messages,
            RepositoryLayoutProposal,
            temperature=0.0,
            max_tokens=5500,
        )

        return result.value



    async def _repair(
        self,
        *,
        tree: RepositoryTree,
        proposal: RepositoryLayoutProposal,
        issue: str,
    ) -> RepositoryLayoutProposal:

        messages: list[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": (
                    _REPAIR_SYSTEM_PROMPT
                    + "\nJSON schema:\n"
                    + json.dumps(
                        RepositoryLayoutPatch.model_json_schema(),
                        ensure_ascii=False,
                    )
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "current_units": [
                            unit.model_dump(mode="json")
                            for unit in proposal.units
                        ],
                        "validation_errors": issue,
                    },
                    ensure_ascii=False,
                ),
            },
        ]

        result = await self._llm.complete_json(
            messages,
            RepositoryLayoutPatch,
            temperature=0.0,
            max_tokens=5500,
        )

        patch = result.value

        logger.info(
            "Discovery repair patch: %s",
            patch.model_dump_json(),
        )

        updated = proposal.model_copy(deep=True)

        units = {
            unit.language_family: unit
            for unit in updated.units
        }

        for change in patch.changes:
            family = _normalize_identifier(
                change.language_family
            )

            unit = units.get(family)

            if unit is None:
                if not change.languages:
                    raise DiscoveryError(
                        f"Missing languages for new family {family}"
                    )

                unit = AnalysisUnitProposal(
                    language_family=family,
                    languages=change.languages,
                    include_patterns=[],
                )

                updated.units.append(unit)
                units[family] = unit

            if change.languages:
                unit.languages = sorted(
                    set(unit.languages) | set(change.languages)
                )

            unit.include_patterns = sorted(
                (
                    set(unit.include_patterns)
                    - set(change.remove_patterns)
                )
                | set(change.add_patterns)
            )

            unit.exclude_patterns = sorted(
                set(unit.exclude_patterns)
                | set(change.add_exclusions)
            )

        if updated == proposal:
            raise DiscoveryError(
                "LLM repair produced no changes. "
                f"Validation errors:\n{issue}"
            )

        return updated


    async def _review(
        self,
        *,
        tree: RepositoryTree,
        layout: RepositoryLayout,
    ) -> RepositoryLayoutReview:

        messages: list[
            ChatCompletionMessageParam
        ] = [
            {
                "role": "system",
                "content": (
                    _REVIEW_SYSTEM_PROMPT
                    + "\n\nJSON schema:\n"
                    + json.dumps(
                        RepositoryLayoutReview.model_json_schema(),
                        ensure_ascii=False,
                    )
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "repository_tree":
                            tree.prompt_view,

                        "resolved_units": [
                            {
                                "language_family":
                                    unit.language_family,

                                "languages":
                                    unit.languages,

                                "source_file_count":
                                    len(unit.source_files),

                                "source_file_examples":
                                    unit.source_files[:10],
                            }
                            for unit in layout.units
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            },
        ]

        result = await self._llm.complete_json(
            messages,
            RepositoryLayoutReview,
            temperature=0.0,
            max_tokens=1000,
        )

        return result.value

    def _resolve(
        self,
        *,
        revision_id: str,
        tree: RepositoryTree,
        proposal: RepositoryLayoutProposal,
    ) -> RepositoryLayout:
        # Glob matching относительно корня репозитория.
        #
        # В отличие от PurePosixPath.match():
        #   src/*.cpp     не совпадает с other/src/file.cpp
        #   **/*.cpp      совпадает и с file.cpp, и с src/file.cpp
        #   src/**/a.cpp  совпадает и с src/a.cpp, и с src/lib/a.cpp

        @lru_cache(maxsize=65536)
        def matches(path: str, pattern: str) -> bool:
            pattern = pattern.strip()

            while pattern.startswith("./"):
                pattern = pattern[2:]

            if not pattern:
                return False

            path_parts = tuple(path.split("/"))
            pattern_parts = tuple(pattern.split("/"))

            @lru_cache(maxsize=None)
            def match(pi: int, gi: int) -> bool:
                if gi == len(pattern_parts):
                    return pi == len(path_parts)

                token = pattern_parts[gi]

                if token == "**":
                    # ** может соответствовать нулю каталогов.
                    if match(pi, gi + 1):
                        return True

                    # Либо одному или нескольким компонентам.
                    return (
                        pi < len(path_parts)
                        and match(pi + 1, gi)
                    )

                if pi >= len(path_parts):
                    return False

                return (
                    fnmatchcase(path_parts[pi], token)
                    and match(pi + 1, gi + 1)
                )

            return match(0, 0)

        if not proposal.units:
            raise DiscoveryError("proposal contains no analysis units")

        # Нормализуем пути один раз.
        repository_files = tuple(sorted(set(tree.files)))

        # Сначала полностью разрешаем каждый unit.
        # Глобальную проверку выполняем только после этого.

        resolved_units = []
        resolved_families = set()

        # file -> language_family
        assigned_files = {}

        overlaps = []

        for proposed_unit in proposal.units:
            family = _normalize_identifier(
                proposed_unit.language_family
            )

            if not family:
                raise DiscoveryError(
                    "analysis unit has empty language_family"
                )

            if family in resolved_families:
                raise DiscoveryError(
                    f"duplicate language_family: {family}"
                )

            resolved_families.add(family)

            languages = tuple(sorted({
                normalized
                for language in proposed_unit.languages
                if (
                    normalized := _normalize_language(language)
                )
            }))

            if not languages:
                raise DiscoveryError(
                    f"no languages specified for family: {family}"
                )

            include_patterns = tuple(
                pattern.strip()
                for pattern in proposed_unit.include_patterns
                if pattern.strip()
            )

            exclude_patterns = tuple(
                pattern.strip()
                for pattern in getattr(
                    proposed_unit,
                    "exclude_patterns",
                    [],
                )
                if pattern.strip()
            )

            if not include_patterns:
                raise DiscoveryError(
                    f"no include_patterns for family: {family}"
                )

            # Объединяем результаты всех include_patterns.
            # Не требуем совпадений для каждого pattern отдельно.

            included = {
                path
                for path in repository_files
                if any(
                    matches(path, pattern)
                    for pattern in include_patterns
                )
            }

            # Применяем exclusions к итоговому набору.

            source_files = tuple(sorted(
                path
                for path in included
                if not any(
                    matches(path, pattern)
                    for pattern in exclude_patterns
                )
            ))

            if not source_files:
                raise DiscoveryError(
                    f"family {family} resolves to zero files; "
                    f"include={include_patterns}, "
                    f"exclude={exclude_patterns}"
                )

            # Проверяем, что файл не попал в разные families.
            # Пересечения внутри одной family допустимы:
            # они уже устранены посредством set.

            for path in source_files:
                previous = assigned_files.get(path)

                if previous is not None:
                    overlaps.append(
                        (path, previous, family)
                    )
                else:
                    assigned_files[path] = family

            resolved_units.append(
                AnalysisUnit(
                    unit_id=make_analysis_unit_id(
                        revision_id=revision_id,
                        language_family=family,
                        source_files=source_files,
                    ),
                    revision_id=revision_id,
                    language_family=family,
                    languages=languages,
                    source_files=source_files,
                )
            )

        # Только сейчас проверяем глобальное покрытие.
        #
        # Проверяем исходники с однозначно определяемой family.
        # Заголовки .h/.hpp намеренно не участвуют в этой проверке.

        uncovered = []
        wrong_family = []

        for file_path in repository_files:
            suffix = PurePosixPath(file_path).suffix
            expected = _SOURCE_EXTENSION_FAMILY.get(suffix)
            if expected is None:
                expected = _SOURCE_EXTENSION_FAMILY.get(suffix.lower())
            if expected is None:
                continue

            actual = assigned_files.get(file_path)

            if actual is None:
                uncovered.append(
                    (file_path, expected)
                )
            elif actual != expected:
                wrong_family.append(
                    (file_path, actual, expected)
                )

        errors = []

        if overlaps:
            errors.append(
                f"overlapping files: {overlaps}"
            )

        if uncovered:
            errors.append(
                f"uncovered files: {uncovered}"
            )

        if wrong_family:
            errors.append(
                f"wrong language families: {wrong_family}"
            )

        if errors:
            raise DiscoveryError(
                "\n".join(errors)
            )

        return RepositoryLayout(
            revision_id=revision_id,
            units=sorted(
                resolved_units,
                key=lambda unit: unit.language_family,
            ),
        )       

def _validate_source_family(
    *,
    file_path: str,
    actual_family: str,
) -> None:

    suffix = PurePosixPath(
        file_path
    ).suffix.lower()

    expected = _SOURCE_EXTENSION_FAMILY.get(
        suffix
    )

    if (
        expected is not None
        and expected != actual_family
    ):
        raise DiscoveryError(
            f"Source file {file_path!r} "
            f"was assigned to {actual_family!r}, "
            f"expected language family "
            f"{expected!r}"
        )


def _format_uncovered_source_files(
    files: list[tuple[str, str]],
) -> str:

    groups: Counter[
        tuple[str, str]
    ] = Counter()

    examples: dict[
        tuple[str, str],
        list[str]
    ] = {}

    for file_path, family in files:
        directory = str(
            PurePosixPath(file_path).parent
        )

        key = (
            family,
            directory,
        )

        groups[key] += 1

        bucket = examples.setdefault(
            key,
            [],
        )

        if len(bucket) < 5:
            bucket.append(file_path)

    parts = [
        "Source files are missing from "
        "the repository layout:"
    ]

    for (
        family,
        directory,
    ), count in groups.most_common():

        sample = ", ".join(
            examples[
                (
                    family,
                    directory,
                )
            ]
        )

        parts.append(
            f"{family}: directory={directory!r}, "
            f"missing={count}, examples=[{sample}]"
        )

    return "\n".join(parts)


def _glob_match(
    path: str,
    pattern: str,
) -> bool:
    candidate = PurePosixPath(path)

    if candidate.match(pattern):
        return True

    if pattern.startswith("**/"):
        return candidate.match(pattern[3:])

    return False
