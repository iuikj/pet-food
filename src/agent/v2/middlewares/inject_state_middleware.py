from typing import Annotated, Any

from langchain.agents.middleware.types import (
    AgentMiddleware,
    ContextT,
)
from langgraph.runtime import Runtime

from src.agent.common.entity.note import Note
from src.agent.v2.state import State
from src.utils.strtuct import PetInformation


class InjectState(State):
    pet_information: Annotated[PetInformation, "宠物信息"]
    count: Annotated[int, "计数"]

class InjectStateMiddleware(AgentMiddleware[InjectState]):
    def before_agent(self, state: InjectState, runtime: Runtime[ContextT]) -> dict[str, Any] | None:
        state['note']={
            "test":Note(content="test",type="research")
        }
        state['count']+=1
        return state.__dict__

    def after_agent(self, state: InjectState, runtime: Runtime[ContextT]) -> dict[str, Any] | None:
        state['count']+=1
        return state.__dict__


