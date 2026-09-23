from __future__ import annotations

import hashlib

from pydantic import BaseModel, Field


class AnalysisUnit(BaseModel):
    unit_id: str
    revision_id: str

    #
    # Canonical lowercase identifiers:
    #
    # clang
    # rust
    # python
    # go
    # js_ts
    # jvm
    # dotnet
    # perl
    # ruby
    # ...
    #
    language_family: str

    #
    # c, cpp, cuda, python, perl, ...
    #
    languages: list[str]

    source_files: list[str] = Field(
        default_factory=list,
    )


class RepositoryLayout(BaseModel):
    revision_id: str
    units: list[AnalysisUnit] = Field(
        default_factory=list,
    )


def make_analysis_unit_id(
    *,
    revision_id: str,
    language_family: str,
    source_files: list[str],
) -> str:

    identity = "\0".join(
        [
            revision_id,
            language_family,
            *sorted(source_files),
        ]
    )

    digest = hashlib.sha256(
        identity.encode("utf-8")
    ).hexdigest()[:20]

    return f"au_{digest}"

class PatternChange(BaseModel):
    language_family: str
    languages: list[str] = Field(default_factory=list)

    add_patterns: list[str] = Field(default_factory=list)
    remove_patterns: list[str] = Field(default_factory=list)

    add_exclusions: list[str] = Field(default_factory=list)


class RepositoryLayoutPatch(BaseModel):
    changes: list[PatternChange]
