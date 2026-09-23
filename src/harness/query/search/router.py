from harness.query.models import (
    EvidenceItem,
    SearchDecision,
)


class SearchRouter:
    async def execute(
        self,
        revision_id: str,
        decision: SearchDecision,
    ) -> list[EvidenceItem]:

        #
        # Пока здесь stub.
        #
        # В следующих итерациях сюда подключим:
        #
        # lexical_search   -> ripgrep
        # semantic_search -> Qdrant
        # find_symbol     -> SCIP
        # find_references -> SCIP
        # find_callers    -> SCIP / language provider
        # find_callees    -> SCIP / language provider
        # data_flow       -> language-specific deep analyzer
        # read_file       -> filesystem reader
        #

        return [
            EvidenceItem(
                type="stub",
                source="stub",
                content=(
                    "Search backend is not connected yet. "
                    f"Requested action={decision.action.value}"
                ),
                symbol_id=decision.symbol_id,
                symbol_name=decision.symbol_name,
                file_path=decision.file_path,
                metadata={
                    "revision_id": revision_id,
                    "query": decision.query or "",
                },
            )
        ]
