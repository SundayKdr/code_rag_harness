import asyncio
from pathlib import Path

from harness.analysis.discovery.manager import (
    DiscoveryManager,
)
from harness.clients.llm import LlmClient
from harness.common.config import get_settings


async def main():
    settings = get_settings()

    llm = LlmClient(settings)

    discovery = DiscoveryManager(llm)

    layout = await discovery.discover(
        revision_id="test_revision",
        revision_root=Path(
            "/home/snd/code-rag-data/materialized/ec30899a-f843-448c-b7b9-d3bd13505521"
        ),
    )

    print(
        layout.model_dump_json(
            indent=2,
        )
    )


asyncio.run(main())
