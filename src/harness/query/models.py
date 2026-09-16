from enum import StrEnum

from pydantic import BaseModel, Field


class QueryIntent(StrEnum):
    FIND_SYMBOL = "find_symbol"
    FIND_IMPLEMENTATION = "find_implementation"
    FIND_USAGE = "find_usage"

    TRACE_CALL_PATH = "trace_call_path"
    TRACE_CREATION = "trace_creation"
    TRACE_DATA_FLOW = "trace_data_flow"

    EXPLAIN_BEHAVIOR = "explain_behavior"

    UNKNOWN = "unknown"


class GraphDirection(StrEnum):
    NONE = "none"
    CALLERS = "callers"
    CALLEES = "callees"
    BOTH = "both"


class QueryPlan(BaseModel):
    original_question: str

    intent: QueryIntent

    entities: list[str] = Field(default_factory=list)
    operations: list[str] = Field(default_factory=list)

    exact_terms: list[str] = Field(default_factory=list)

    semantic_queries: list[str] = Field(
        default_factory=list,
        min_length=1,
        max_length=5,
    )

    needs_graph_expansion: bool = False

    graph_direction: GraphDirection = GraphDirection.NONE

    max_graph_depth: int = Field(
        default=0,
        ge=0,
        le=4,
    )

class AskRequest(BaseModel):
    revision_id: str = Field(
        min_length=1,
    )

    question: str = Field(
        min_length=1,
        max_length=20_000,
    )

class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

class AskResponse(BaseModel):
    request_id: str
    revision_id: str
    answer: str
    query_plan: QueryPlan
    usage: TokenUsage

class HealthResponse(BaseModel):
    status: str
    llm_status: str
    llm_model: str

