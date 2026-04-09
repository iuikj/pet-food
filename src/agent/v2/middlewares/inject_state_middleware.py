from langchain.agents.middleware import AgentMiddleware
from src.agent.v2.state import State

class InjectStateMiddleware(AgentMiddleware):
    state_schema = State