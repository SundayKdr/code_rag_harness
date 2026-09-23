from pydantic import BaseModel, Field


class AnalysisUnitProposal(BaseModel):
    language_family: str

    languages: list[str]

    include_patterns: list[str] = Field(
        default_factory=list,
    )
    exclude_patterns: list[str] = Field(
        default_factory=list,
    )


class RepositoryLayoutProposal(BaseModel):
    units: list[AnalysisUnitProposal] = Field(
        default_factory=list,
    )


class RepositoryLayoutReview(BaseModel):
    valid: bool

    issues: list[str] = Field(
        default_factory=list,
        max_length=5,
    )
