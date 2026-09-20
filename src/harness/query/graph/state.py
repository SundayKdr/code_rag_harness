from typing import Any, TypedDict


class HarnessState(TypedDict, total=False):
    request_id: str
    revision_id: str
    repository_id: str
    commit_sha: str

    question: str

    query_plan: dict[str, Any]

    iteration: int
    max_iterations: int

    search_decision: dict[str, Any]
    evidence_evaluation: dict[str, Any]

    evidence: list[dict[str, Any]]
    search_trace: list[dict[str, Any]]

    answer: str

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    error: str
