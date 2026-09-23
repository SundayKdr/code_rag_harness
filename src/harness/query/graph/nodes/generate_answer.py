import json
from collections.abc import Awaitable, Callable

from openai.types.chat import ChatCompletionMessageParam

from harness.clients.llm import LlmClient
from harness.query.graph.state import HarnessState


NodeCallable = Callable[
    [HarnessState],
    Awaitable[dict[str, object]],
]


def build_generate_answer_node(
    llm: LlmClient,
) -> NodeCallable:

    async def generate_answer(
        state: HarnessState,
    ) -> dict[str, object]:

        messages: list[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": (
                    "You are the final answer generator of a "
                    "source-code analysis system. "
                    "Answer only from the provided evidence. "
                    "Do not invent repository facts. "
                    "If evidence is insufficient, explicitly state "
                    "what could not be established."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "question": state["question"],
                        "query_plan":
                            state["query_plan"],
                        "evidence":
                            state.get("evidence", []),
                        "evaluation":
                            state.get(
                                "evidence_evaluation"
                            ),
                        "search_trace":
                            state.get(
                                "search_trace", []
                            ),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            },
        ]

        result = await llm.complete(
            messages,
            temperature=0.1,
        )

        return {
            "answer": result.text,

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

    return generate_answer
