
from collections.abc import Awaitable, Callable

from openai.types.chat import ChatCompletionMessageParam

from harness.clients.llm import LlmClient
from harness.query.graph.state import HarnessState


NodeCallable = Callable[[HarnessState], Awaitable[dict[str, object]]]


def build_direct_answer_node(llm: LlmClient) -> NodeCallable:
    async def direct_answer(state: HarnessState) -> dict[str, object]:
        question = state["question"]

        messages: list[ChatCompletionMessageParam] = [
            {
                "role": "system",
                "content": (
                    "Ты являешься основной моделью системы анализа кодовой базы. "
                    "Сейчас retrieval ещё не подключён, поэтому не утверждай, "
                    "что знаешь содержимое конкретного репозитория. "
                    "Отвечай на текущий вопрос прямо и технически точно."
                ),
            },
            {
                "role": "user",
                "content": question,
            },
        ]

        result = await llm.complete(messages)

        return {
            "answer": result.text,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "total_tokens": result.total_tokens,
        }

    return direct_answer
