import json
from collections.abc import Awaitable, Callable

from openai.types.chat import ChatCompletionMessageParam

from harness.clients.llm import LlmClient
from harness.query.graph.state import HarnessState
from harness.query.models import EvidenceEvaluation


NodeCallable = Callable[
    [HarnessState],
    Awaitable[dict[str, object]],
]


SYSTEM_PROMPT = """
You evaluate whether gathered source-code evidence is sufficient
to answer the user's original question accurately.

Do NOT answer the question.

Determine:

- whether the evidence is sufficient;
- what information is still missing;
- which retrieval operations would be useful next.

Evidence whose source is "stub" is NOT real source-code evidence
and must never be considered sufficient.

Do not request information which is already present.

Return ONLY valid JSON matching the schema.
""".strip()


def build_evaluate_evidence_node(
    llm: LlmClient,
) -> NodeCallable:

    async def evaluate_evidence(
        state: HarnessState,
    ) -> dict[str, object]:

        messages: list[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": (
                    SYSTEM_PROMPT
                    + "\n\nJSON schema:\n"
                    + json.dumps(
                        EvidenceEvaluation.model_json_schema(),
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
                        "iteration": state["iteration"],
                        "max_iterations": state["max_iterations"],
                        "evidence": state.get(
                            "evidence", []
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
            EvidenceEvaluation,
            temperature=0.0,
            max_tokens=600,
        )

        return {
            "evidence_evaluation":
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

    return evaluate_evidence
