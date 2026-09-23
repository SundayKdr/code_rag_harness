import json
from collections.abc import Awaitable, Callable

from openai.types.chat import ChatCompletionMessageParam

from harness.clients.llm import LlmClient
from harness.query.graph.state import HarnessState
from harness.query.models import SearchDecision


NodeCallable = Callable[
    [HarnessState],
    Awaitable[dict[str, object]],
]


SYSTEM_PROMPT = """
You are the search planner of a source-code analysis agent.

Your job is to decide exactly ONE next retrieval action.

You do NOT answer the user's question.

Available actions:

lexical_search:
    Search exact text or identifiers.

semantic_search:
    Search code semantically when the exact symbol is unknown.

find_symbol:
    Resolve a symbol definition.

find_references:
    Find references to a known symbol.

find_callers:
    Find functions which call a known function.

find_callees:
    Find functions called by a known function.

data_flow:
    Trace where a value comes from or where it goes.

read_file:
    Read source around a known location.

finish:
    No additional retrieval is required.

Important strategy:

When you do not know the relevant symbol, prefer broad
lexical or semantic discovery.

Once a useful symbol has been found, prefer precise
symbol/reference/call-graph operations rather than repeatedly
running semantic search.

Do not repeat a search that already appears in search_trace.

Use FINISH only if current evidence is enough to answer the
original question.

Return ONLY valid JSON matching the schema.
""".strip()


def build_plan_search_node(
    llm: LlmClient,
) -> NodeCallable:

    async def plan_search(
        state: HarnessState,
    ) -> dict[str, object]:

        messages: list[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": (
                    SYSTEM_PROMPT
                    + "\n\nJSON schema:\n"
                    + json.dumps(
                        SearchDecision.model_json_schema(),
                        ensure_ascii=False,
                    )
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "question": state["question"],
                        "query_plan": state["query_plan"],
                        "iteration": state.get(
                            "iteration", 0
                        ),
                        "max_iterations": state[
                            "max_iterations"
                        ],
                        "evidence": state.get(
                            "evidence", []
                        ),
                        "previous_evaluation": state.get(
                            "evidence_evaluation"
                        ),
                        "search_trace": state.get(
                            "search_trace", []
                        ),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            },
        ]

        result = await llm.complete_json(
            messages,
            SearchDecision,
            temperature=0.0,
            max_tokens=600,
        )

        return {
            "search_decision":
                result.value.model_dump(),

            "prompt_tokens": (
                state.get("prompt_tokens", 0)
                + result.prompt_tokens
            ),

            "completion_tokens": (
                state.get("completion_tokens", 0)
                + result.completion_tokens
            ),

            "total_tokens": (
                state.get("total_tokens", 0)
                + result.total_tokens
            ),
        }

    return plan_search
