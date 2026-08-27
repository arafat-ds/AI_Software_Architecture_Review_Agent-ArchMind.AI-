"""
ArchMind AI — OpenWebUI Pipeline (F1 stub).

Loads and registers with the Pipelines server. Exposes Valves form in the admin
panel. Yields a placeholder response. Analysis logic arrives in F2.
"""

from typing import AsyncGenerator

from pydantic import BaseModel


class Pipeline:
    name = "ArchMind AI"
    version = "1.0.0"
    # ⚠ VERIFY AT F1: whether type attribute is required and its value
    # type = "pipe"

    class Valves(BaseModel):
        ARCHMIND_API_URL: str = "http://backend:8000"
        ARCHMIND_API_KEY: str = ""
        POLL_INTERVAL_SECONDS: int = 5
        MAX_POLL_DURATION_SECONDS: int = 1800

    def __init__(self):
        self.valves = self.Valves()

    async def on_startup(self):
        print(f"[ArchMind] Pipeline startup — API URL: {self.valves.ARCHMIND_API_URL}")

    async def on_shutdown(self):
        print("[ArchMind] Pipeline shutdown")

    async def on_valves_updated(self):
        print(f"[ArchMind] Valves updated — API URL: {self.valves.ARCHMIND_API_URL}")

    async def pipe(
        self,
        user_message: str,
        model_id: str,
        messages: list[dict],
        body: dict,
    ) -> AsyncGenerator[str, None]:
        yield "ArchMind AI pipeline loaded. Analysis logic arrives in F2."
