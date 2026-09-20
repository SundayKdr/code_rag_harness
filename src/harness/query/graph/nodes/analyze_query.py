import json
from collections.abc import Awaitable, Callable

from openai.types.chat import ChatCompletionMessageParam

from harness.clients.llm import LlmClient
from harness.query.graph.state import HarnessState
from harness.query.models import QueryPlan


NodeCallable = Callable[
    [HarnessState],
    Awaitable[dict[str, object]],
]


SYSTEM_PROMPT = """
You are a query planner for a source-code retrieval system.

You must analyze the user's question.
You must NOT answer the user's question.

The target is a large C/C++ codebase.

The retrieval system will later have access to:
- semantic vector search
- lexical search
- symbol search
- call graph traversal
- data-flow analysis

Produce a retrieval plan.

Rules:

exact_terms:
- Put explicit identifiers, class names, function names, field names,
  macros and literal strings here.
- Do not invent identifiers which were not present in the question.

semantic_queries:
- Generate between 1 and 5 self-contained English search queries.
- Describe the code behavior which could answer the user's question.
- Do not assume exact implementation names.
- Queries should be suitable for semantic embedding retrieval.

entities:
- Extract conceptual program entities.
- Examples: flow, TCP session, packet, connection, parser,
  configuration, buffer.

operations:
- Describe expected operations.
- Examples: lookup, allocate, create, initialize, insert, update,
  parse, validate, free, dispatch, call, return.

intent:
Choose exactly one:
- find_symbol
- find_implementation
- find_usage
- trace_call_path
- trace_creation
- trace_data_flow
- explain_behavior
- unknown

needs_graph_expansion:
- true if the answer is likely to require callers, callees,
  or following several functions.

graph_direction:
- none
- callers
- callees
- both

Guidelines:

"where is X defined"
-> find_symbol

"where is X called"
-> find_usage, callers

"what does X do internally"
-> explain_behavior, callees

"how does X get created"
-> trace_creation, usually both

"where does value X come from"
-> trace_data_flow

max_graph_depth:
- 0 if graph traversal is unnecessary.
- Usually 1 or 2.
- Maximum 4.

Return ONLY valid JSON matching the supplied schema.
Do not use markdown.
Do not add explanatory text.
""".strip()


def build_analyze_query_node(
    llm: LlmClient,
) -> NodeCallable:

    async def analyze_query(
        state: HarnessState,
    ) -> dict[str, object]:

        question = state["question"]

        schema = QueryPlan.model_json_schema()

        messages: list[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": (
                    SYSTEM_PROMPT
                    + "\n\nJSON schema:\n"
                    + json.dumps(
                        schema,
                        ensure_ascii=False,
                    )
                ),
            },
            {
                "role": "user",
                "content": question,
            },
        ]

        result = await llm.complete_json(
			messages,
		    QueryPlan,
		    temperature=0.0,
		    max_tokens=1200,
		)

        plan = result.value
        plan.original_question = question

        return {
            "query_plan": plan.model_dump(),
            "prompt_tokens": (
                state.get("prompt_tokens", 0) + result.prompt_tokens
            ),
            "completion_tokens": (
                state.get("completion_tokens", 0) + result.completion_tokens
            ),
            "total_tokens": (
                state.get("total_tokens", 0) + result.total_tokens
            ),
        }    	          
    return analyze_query
