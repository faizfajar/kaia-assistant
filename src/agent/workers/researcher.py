from langchain_google_genai import ChatGoogleGenerativeAI
from src.agent.state import AgentState
from src.agent.prompts import RESEARCHER_PROMPT
from src.tools import search_knowledge, add_document_to_db

# Define the researcher node
def researcher_node(state: AgentState):
    """
    Worker node specialized in RAG and document retrieval.
    Processes the user query and searches the internal knowledge base.
    """
    
    # Initialize the LLM specifically for this worker
    # We can use a smaller model here to save costs if needed
    llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite-preview", temperature=0)
    
    # Bind the retrieval tool
    tools = [search_knowledge, add_document_to_db]
    llm_with_tools = llm.bind_tools(tools)
    
    # Get the last message from the thread to process
    last_message = state["messages"][-1]
    
    # System prompt provides identity and constraints
    system_message = {"role": "system", "content": RESEARCHER_PROMPT}
    
    # Execute the LLM call with history and system context
    response = llm_with_tools.invoke([system_message] + state["messages"])
    
    # Return the updated message list to the global state
    return {"messages": [response]}