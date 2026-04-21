from typing import Annotated, Sequence, TypedDict, Literal
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    """
    Maintains the state of the multi-agent conversation.
    This structure is passed between the supervisor and specialized workers.
    """
    
    # Conversation history with automatic message merging logic
    messages: Annotated[Sequence[BaseMessage], add_messages]
    
    # Routing control: Determines which node is activated next in the graph
    # Options include the specialist names or 'FINISH' to end the cycle
    next: Literal["Researcher", "Secretary", "DevOps", "News", "FINISH"]