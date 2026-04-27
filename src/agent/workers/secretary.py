from langchain_google_genai import ChatGoogleGenerativeAI
from src.agent.state import AgentState
from src.agent.prompts import get_secretary_prompt
from src.tools import save_note, get_notes, delete_note, get_current_datetime

# Module-level instantiation — avoids re-creating LLM on every node call
_llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite-preview",
    temperature=0
)

_tools = [save_note, get_notes, delete_note, get_current_datetime]
_llm_with_tools = _llm.bind_tools(_tools)


def secretary_node(state: AgentState) -> dict:
    """
    Worker node for task management, notes, and scheduling.
    
    Sets active_worker so call_tool knows to return here
    after tool execution instead of routing back to Supervisor.
    """
    system_message = {"role": "system", "content": get_secretary_prompt()}
    response = _llm_with_tools.invoke([system_message] + list(state["messages"]))

    return {
        "messages": [response],
        "active_worker": "Secretary"
    }