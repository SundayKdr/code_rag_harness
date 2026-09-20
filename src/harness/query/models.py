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

class SearchAction(StrEnum):
    LEXICAL_SEARCH = "lexical_search"
    SEMANTIC_SEARCH = "semantic_search"
    FIND_SYMBOL = "find_symbol"
    FIND_REFERENCES = "find_references"
    FIND_CALLERS = "find_callers"
    FIND_CALLEES = "find_callees"
    DATA_FLOW = "data_flow"
    READ_FILE = "read_file"
    FINISH = "finish"

class SearchRecord(BaseModel):
    iteration: int
    action: SearchAction
    query: str | None = None
    symbol_id: str | None = None
    symbol_name: str | None = None
    file_path: str | None = None
    result_count: int = 0
    error: str | None = None

class SearchDecision(BaseModel):
    action: SearchAction
    query: str | None = None
    symbol_id: str | None = None
    symbol_name: str | None = None
    file_path: str | None = None
    rationale: str
    expected_evidence: str


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
    search_trace: list[SearchRecord] = Field(
        default_factory=list,
    )
    usage: TokenUsage

class HealthResponse(BaseModel):
    status: str
    llm_status: str
    llm_model: str

class EvidenceItem(BaseModel):
    type: str
    source: str

    content: str

    symbol_id: str | None = None
    symbol_name: str | None = None

    file_path: str | None = None
    start_line: int | None = None
    end_line: int | None = None

    metadata: dict[str, str] = Field(
        default_factory=dict,
    )


class EvidenceEvaluation(BaseModel):
    sufficient: bool

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    missing_information: list[str] = Field(
        default_factory=list,
    )

    suggested_actions: list[SearchAction] = Field(
        default_factory=list,
    )
