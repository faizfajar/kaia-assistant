from langchain_google_genai import ChatGoogleGenerativeAI
from src.agent.state import AgentState
from src.agent.prompts import SECRETARY_PROMPT
from src.tools import save_note, get_notes, delete_note, get_current_datetime

def secretary_node(state: AgentState):
    """
    Worker node specialized in task management, notes, and scheduling.
    Ensures user's personal administrative tasks are handled efficiently.
    """
    
    llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite-preview", temperature=0)
    
    # Bind administrative tools
    tools = [save_note, get_notes, delete_note, get_current_datetime]
    llm_with_tools = llm.bind_tools(tools)
    
    system_message = {"role": "system", "content": SECRETARY_PROMPT}
    
    # Process the conversation history
    response = llm_with_tools.invoke([system_message] + state["messages"])
    
    return {"messages": [response]}