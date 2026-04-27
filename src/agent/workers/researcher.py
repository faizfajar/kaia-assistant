from langchain_google_genai import ChatGoogleGenerativeAI
from src.agent.state import AgentState
from src.agent.prompts import get_researcher_prompt
from src.tools import search_knowledge, add_document_to_db

# Module-level instantiation — avoid re-creating LLM on every node call
_llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite-preview",
    temperature=0
)

_tools = [search_knowledge, add_document_to_db]
_llm_with_tools = _llm.bind_tools(_tools)


def researcher_node(state: AgentState) -> dict:
    """
    Worker node for RAG-based knowledge retrieval and document search.

    Sets active_worker so call_tool knows to return here
    after tool execution instead of routing back to Supervisor.
    """
    system_message = {"role": "system", "content": get_researcher_prompt()}
    response = _llm_with_tools.invoke([system_message] + list(state["messages"]))

    return {
        "messages": [response],
        "active_worker": "Researcher"
    }