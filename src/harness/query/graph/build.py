from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from harness.clients.llm import LlmClient
from harness.query.graph.nodes.analyze_query import (
    build_analyze_query_node,
)
from harness.query.graph.nodes.evaluate_evidence import (
    build_evaluate_evidence_node,
)
from harness.query.graph.nodes.execute_search import (
    build_execute_search_node,
)
from harness.query.graph.nodes.generate_answer import (
    build_generate_answer_node,
)
from harness.query.graph.nodes.plan_search import (
    build_plan_search_node,
)
from harness.query.graph.state import HarnessState
from harness.query.models import (
    EvidenceEvaluation,
    SearchAction,
    SearchDecision,
)
from harness.query.search.router import SearchRouter


def _route_after_plan(
    state: HarnessState,
) -> Literal[
    "execute_search",
    "generate_answer",
]:

    decision = SearchDecision.model_validate(
        state["search_decision"]
    )

    if decision.action == SearchAction.FINISH:
        return "generate_answer"

    return "execute_search"


def _route_after_evaluation(
    state: HarnessState,
) -> Literal[
    "plan_search",
    "generate_answer",
]:

    if (
        state.get("iteration", 0)
        >= state["max_iterations"]
    ):
        return "generate_answer"

    evaluation = EvidenceEvaluation.model_validate(
        state["evidence_evaluation"]
    )

    if evaluation.sufficient:
        return "generate_answer"

    return "plan_search"


def build_graph(
    llm: LlmClient,
    search_router: SearchRouter,
) -> CompiledStateGraph:

    builder = StateGraph(HarnessState)

    builder.add_node(
        "analyze_query",
        build_analyze_query_node(llm),
    )

    builder.add_node(
        "plan_search",
        build_plan_search_node(llm),
    )

    builder.add_node(
        "execute_search",
        build_execute_search_node(
            search_router
        ),
    )

    builder.add_node(
        "evaluate_evidence",
        build_evaluate_evidence_node(llm),
    )

    builder.add_node(
        "generate_answer",
        build_generate_answer_node(llm),
    )

    builder.add_edge(
        START,
        "analyze_query",
    )

    builder.add_edge(
        "analyze_query",
        "plan_search",
    )

    builder.add_conditional_edges(
        "plan_search",
        _route_after_plan,
    )

    builder.add_edge(
        "execute_search",
        "evaluate_evidence",
    )

    builder.add_conditional_edges(
        "evaluate_evidence",
        _route_after_evaluation,
    )

    builder.add_edge(
        "generate_answer",
        END,
    )

    return builder.compile()
