from typing import Any

from langchain.agents.middleware import AgentState,AgentMiddleware
from langchain.agents.middleware.types import StateT
from langgraph.runtime import Runtime
from langgraph.typing import ContextT


class ProgressMiddleware(AgentMiddleware):

    def after_model(self, state: StateT, runtime: Runtime[ContextT]) -> dict[str, Any] | None:
        pass