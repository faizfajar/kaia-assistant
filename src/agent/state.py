from typing import Annotated, Sequence, TypedDict, Literal
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """
    Shared state passed between all nodes in the multi-agent graph.
    
    - messages: Full conversation history, auto-merged via add_messages reducer
    - next: Supervisor's routing decision for the current turn
    - active_worker: Tracks which worker last requested a tool call,
                     enabling call_tool to return to the correct worker
                     instead of routing back through Supervisor.
    """
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next: Literal["Researcher", "Secretary", "DevOps", "News", "FINISH"]
    active_worker: Literal["Researcher", "Secretary", "DevOps", "News", ""]