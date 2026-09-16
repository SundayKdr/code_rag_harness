from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from harness.clients.llm import LlmClient
from harness.query.graph.nodes.analyze_query import (
    build_analyze_query_node,
)
from harness.query.graph.nodes.direct_answer import (
    build_direct_answer_node,
)
from harness.query.graph.state import HarnessState


def build_graph(
    llm: LlmClient,
) -> CompiledStateGraph:

    builder = StateGraph(HarnessState)

    builder.add_node(
        "analyze_query",
        build_analyze_query_node(llm),
    )

    builder.add_node(
        "direct_answer",
        build_direct_answer_node(llm),
    )

    builder.add_edge(
        START,
        "analyze_query",
    )

    builder.add_edge(
        "analyze_query",
        "direct_answer",
    )

    builder.add_edge(
        "direct_answer",
        END,
    )

    return builder.compile()
