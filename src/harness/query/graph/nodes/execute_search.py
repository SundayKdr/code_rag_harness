from collections.abc import Awaitable, Callable

from harness.query.graph.state import HarnessState
from harness.query.models import (
    SearchDecision,
    SearchRecord,
)
from harness.query.search.router import SearchRouter


NodeCallable = Callable[
    [HarnessState],
    Awaitable[dict[str, object]],
]


def build_execute_search_node(
    router: SearchRouter,
) -> NodeCallable:

    async def execute_search(
        state: HarnessState,
    ) -> dict[str, object]:

        decision = SearchDecision.model_validate(
            state["search_decision"]
        )

        iteration = state.get(
            "iteration", 0
        ) + 1

        evidence = await router.execute(
            revision_id=state["revision_id"],
            decision=decision,
        )

        record = SearchRecord(
            iteration=iteration,
            action=decision.action,
            query=decision.query,
            symbol_id=decision.symbol_id,
            symbol_name=decision.symbol_name,
            file_path=decision.file_path,
            result_count=len(evidence),
        )

        previous_evidence = state.get(
            "evidence", []
        )

        previous_trace = state.get(
            "search_trace", []
        )

        return {
            "iteration": iteration,

            "evidence": (
                previous_evidence
                + [
                    item.model_dump()
                    for item in evidence
                ]
            ),

            "search_trace": (
                previous_trace
                + [record.model_dump()]
            ),
        }

    return execute_search
