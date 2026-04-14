import os
from typing import Annotated
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, BaseMessage

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from typing_extensions import TypedDict

from src.agent.persona import KAIA_SYSTEM_PROMPT
from src.tools import ALL_TOOLS

load_dotenv()

# ── LLM Setup ──────────────────────────────────────────────────────────────────

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.7
)

llm_with_tools = llm.bind_tools(ALL_TOOLS)

# ── State Definition ───────────────────────────────────────────────────────────

class KaiaState(TypedDict):
    """
    State that flows through the graph.
    Every node reads from and writes to this state.

    'messages' uses add_messages reducer — meaning each node
    appends to the list rather than replacing it entirely.
    This is called a 'reducer' in LangGraph terminology.
    """
    messages: Annotated[list[BaseMessage], add_messages]
    user_name: str
    memory_summary: str


# ── Prompt Template ────────────────────────────────────────────────────────────

prompt = ChatPromptTemplate.from_messages([
    ("system", KAIA_SYSTEM_PROMPT),
    MessagesPlaceholder(variable_name="messages"),
])


# ── Node Definitions ───────────────────────────────────────────────────────────

def llm_node(state: KaiaState) -> dict:
    """
    LLM Node — the reasoning step of the ReAct pattern.

    Receives current state, formats the prompt with persona context,
    invokes the LLM, and returns the response to be appended to state.
    """
    formatted = prompt.invoke({
        "user_name": state["user_name"],
        "memory_summary": state["memory_summary"],
        "messages": state["messages"],
    })

    response = llm_with_tools.invoke(formatted)
    return {"messages": [response]}


# ToolNode is a prebuilt LangGraph node that handles tool execution.
# It automatically reads tool_calls from the last message,
# executes the corresponding tools, and returns ToolMessages.
tool_node = ToolNode(ALL_TOOLS)


# ── Routing / Conditional Edge ─────────────────────────────────────────────────

def should_use_tools(state: KaiaState) -> str:
    """
    Conditional edge function — the routing decision point.

    Checks if the last LLM message contains tool_calls.
    Returns the name of the next node to visit:
    - "tools"  → LLM wants to call a tool (continue the loop)
    - END      → LLM has a final answer (exit the graph)

    This is the core of the ReAct loop:
    Reason (llm_node) → decide → Act (tool_node) → back to Reason
    """
    last_message = state["messages"][-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    return END


# ── Graph Construction ─────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Construct and compile the LangGraph agent graph.

    Graph structure:
        [START] → [llm_node] → should_use_tools?
                                    ↙         ↘
                             [tool_node]      [END]
                                    ↓
                              [llm_node]  ← loops back
    """
    graph = StateGraph(KaiaState)

    # Register nodes
    graph.add_node("llm", llm_node)
    graph.add_node("tools", tool_node)

    # Entry point — graph always starts at llm node
    graph.set_entry_point("llm")

    # Conditional edge from llm — route based on should_use_tools()
    graph.add_conditional_edges(
        source="llm",
        path=should_use_tools,
        path_map={"tools": "tools", END: END}
    )

    # Fixed edge — after tools always go back to llm
    # This creates the ReAct loop
    graph.add_edge("tools", "llm")

    return graph.compile()


# Compile once at module load — reused for every invocation
kaia_graph = build_graph()


# ── Public Interface ───────────────────────────────────────────────────────────

def invoke_kaia(
    user_input: str,
    user_name: str,
    memory_summary: str,
    chat_history: list
) -> str:
    """
    Public interface for invoking Kaia via the LangGraph agent.

    Constructs initial state and runs the graph until END.
    The graph handles all tool calling and looping internally.

    Args:
        user_input: Latest message from the user.
        user_name: Name of the user (injected into persona).
        memory_summary: Long-term memory summary (injected into persona).
        chat_history: Previous messages in this session.

    Returns:
        Kaia's final text response.
    """
    initial_state: KaiaState = {
        "messages": [*chat_history, HumanMessage(content=user_input)],
        "user_name": user_name,
        "memory_summary": memory_summary,
    }

    final_state = kaia_graph.invoke(initial_state)

    # Extract the last message — this is Kaia's final response
    last_message = final_state["messages"][-1]
    return last_message.content