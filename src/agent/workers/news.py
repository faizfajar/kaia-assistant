from langchain_google_genai import ChatGoogleGenerativeAI
from src.agent.state import AgentState
from src.agent.prompts import NEWS_PROMPT
from src.tools.news_tools import search_news

# Module-level instantiation
_llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite-preview",
    temperature=0
)

_tools = [search_news]
_llm_with_tools = _llm.bind_tools(_tools)

def news_node(state: AgentState) -> dict:
    """
    Worker node for fetching and synthesizing news (Tech, Sports, Politics).
    
    Sets active_worker so call_tool knows to return here
    after tool execution instead of routing back to Supervisor.
    """
    system_message = {"role": "system", "content": NEWS_PROMPT}
    response = _llm_with_tools.invoke([system_message] + list(state["messages"]))

    return {
        "messages": [response],
        "active_worker": "News"
    }
