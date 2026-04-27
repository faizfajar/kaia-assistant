import os
import sys
import asyncio
import logging
from typing import Literal, Annotated, Sequence
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode

from mcp import StdioServerParameters
from src.agent.mcp_adapter import MCPToolAdapter

from src.agent.state import AgentState
from src.agent.prompts import get_supervisor_prompt
from src.agent.workers.researcher import researcher_node
from src.agent.workers.secretary import secretary_node
from src.agent.workers.devops import get_devops_node
from src.agent.workers.news import news_node
from src.tools import ALL_TOOLS

load_dotenv()

# ── Supervisor Structured Output Schema ────────────────────────────────────────

class RouterConfig(BaseModel):
    """Schema for the Supervisor's routing decision."""
    next: Literal["Researcher", "Secretary", "DevOps", "News", "FINISH"] = Field(
        description="The next specialist to act, or FINISH if the request is satisfied."
    )

# ── LLM Setup ──────────────────────────────────────────────────────────────────

llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite-preview",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.1
)

structured_llm = llm.with_structured_output(RouterConfig)

# ── MCP Tool Initialization (Lazy, Cached) ─────────────────────────────────────

GITHUB_SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=[os.path.abspath("servers/github_server.py")],
    env={**os.environ}
)

_github_tools_cache: list | None = None

def get_github_tools() -> list:
    """
    Lazy-load GitHub MCP tools from the stdio server.
    Cached after first successful call to avoid repeated startup cost.
    Falls back to empty list if MCP server is unavailable.
    """
    global _github_tools_cache

    if _github_tools_cache is None:
        adapter = MCPToolAdapter(GITHUB_SERVER_PARAMS)
        try:
            _github_tools_cache = asyncio.run(adapter.get_tools())
            logging.info(f"Loaded {len(_github_tools_cache)} MCP tools from GitHub server.")
        except Exception as e:
            logging.error(f"Failed to load MCP tools: {e}")
            _github_tools_cache = []

    return _github_tools_cache


GITHUB_TOOLS = get_github_tools()
EXTENDED_TOOLS = ALL_TOOLS + GITHUB_TOOLS

# ── Node Definitions ───────────────────────────────────────────────────────────

def supervisor_node(state: AgentState) -> dict:
    """
    Lead Orchestrator.
    Reads the latest user message and routes to the appropriate specialist.
    Uses structured output to enforce strict JSON routing — no free text.
    Falls back to FINISH on any parsing error to prevent infinite loops.
    """
    system_message = {"role": "system", "content": get_supervisor_prompt()}

    try:
        decision = structured_llm.invoke([system_message] + list(state["messages"]))
        return {"next": decision.next}
    except Exception as e:
        logging.error(f"Supervisor routing error: {e}")
        return {"next": "FINISH"}


# Factory pattern — injects dynamic MCP tools into DevOps worker at build time
devops_node = get_devops_node(llm, GITHUB_TOOLS)

# Centralized tool execution node for all workers
tool_node = ToolNode(EXTENDED_TOOLS)

# ── Routing Functions ──────────────────────────────────────────────────────────

def router(state: AgentState) -> Literal["Researcher", "Secretary", "DevOps", "News", "FINISH"]:
    """
    Entry router — dispatches from Supervisor to the correct specialist.
    Maps supervisor's next decision directly to graph node names.
    """
    return state["next"]


def worker_should_continue(state: AgentState) -> Literal["call_tool", "FINISH"]:
    """
    Post-worker routing decision.

    Two possible outcomes:
    - call_tool: Worker requested a tool — execute it
    - FINISH:    Worker produced a text response — return to user

    Note: FINISH here does not mean "close the session". It means
    "return this response to the user and wait for the next input."
    The session continues on the next invoke_kaia() call.
    """
    last_message = state["messages"][-1]

    # Worker requested tool execution
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "call_tool"

    # Worker produced a final text response — exit graph
    if isinstance(last_message, AIMessage) and last_message.content:
        return "FINISH"

    # Fallback — should not normally reach here
    return "FINISH"


def after_tool(state: AgentState) -> str:
    """
    Post-tool routing — returns to whichever worker requested the tool.

    This prevents unnecessary Supervisor re-evaluation after every
    tool execution, which was the primary cause of token waste and
    infinite loops in the previous architecture.

    Falls back to Supervisor only if active_worker is unset.
    """
    active = state.get("active_worker", "")

    if active in ("Secretary", "DevOps", "Researcher", "News"):
        return active

    # Safety fallback — active_worker not set, re-evaluate from Supervisor
    logging.warning("active_worker not set after tool execution, routing to Supervisor.")
    return "Supervisor"

# ── Graph Construction ─────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Construct and compile the multi-agent LangGraph workflow.

    Graph structure:

        [START] → [Supervisor] → router() → [Secretary / DevOps / Researcher / News]
                                                        ↓
                                               worker_should_continue()
                                                ↙               ↘
                                         [call_tool]          [END]
                                              ↓
                                         after_tool()
                                              ↓
                              back to active worker (not Supervisor)
    """
    workflow = StateGraph(AgentState)

    # Register nodes
    workflow.add_node("Supervisor", supervisor_node)
    workflow.add_node("Researcher", researcher_node)
    workflow.add_node("Secretary", secretary_node)
    workflow.add_node("DevOps", devops_node)
    workflow.add_node("News", news_node)
    workflow.add_node("call_tool", tool_node)

    # Entry point
    workflow.set_entry_point("Supervisor")

    # Supervisor → specialist routing
    workflow.add_conditional_edges(
        "Supervisor",
        router,
        {
            "Researcher": "Researcher",
            "Secretary": "Secretary",
            "DevOps": "DevOps",
            "News": "News",
            "FINISH": END
        }
    )

    # Worker → tool or END
    for worker in ["Researcher", "Secretary", "DevOps", "News"]:
        workflow.add_conditional_edges(
            worker,
            worker_should_continue,
            {
                "call_tool": "call_tool",
                "FINISH": END
            }
        )

    # Tool → back to active worker (not Supervisor)
    workflow.add_conditional_edges(
        "call_tool",
        after_tool,
        {
            "Secretary": "Secretary",
            "DevOps": "DevOps",
            "Researcher": "Researcher",
            "News": "News",
            "Supervisor": "Supervisor"   # safety fallback only
        }
    )

    return workflow.compile()


kaia_graph = build_graph()

# ── Public API ─────────────────────────────────────────────────────────────────

def invoke_kaia(user_input: str, chat_history: list) -> str:
    """
    Main entry point for processing a single user message.

    Slices new messages from final state to avoid re-processing history.
    Prioritizes AIMessage content over raw ToolMessage output.
    """
    # Track where new messages start after this invocation
    start_index = len(chat_history) + 1

    initial_state: AgentState = {
        "messages": [*chat_history, HumanMessage(content=user_input)],
        "next": "Supervisor",
        "active_worker": ""
    }

    try:
        final_state = kaia_graph.invoke(initial_state)
        messages = final_state.get("messages", [])
        new_messages = messages[start_index:]

        # Priority 1 — AI summary response
        for msg in reversed(new_messages):
            if isinstance(msg, AIMessage) and msg.content:
                content = msg.content
                if isinstance(content, list):
                    content = "".join([
                        b.get("text", "") if isinstance(b, dict) else str(b)
                        for b in content
                    ])
                if isinstance(content, str) and content.strip():
                    return content.strip()

        # Priority 2 — Raw tool output (fallback for save_note / GitHub)
        for msg in reversed(new_messages):
            if isinstance(msg, ToolMessage) and msg.content:
                return str(msg.content).strip()

        return "Selesai! Ada lagi yang bisa aku bantu, Faiz?"

    except Exception as e:
        if "503" in str(e):
            return "Server Gemini lagi sibuk, coba lagi sebentar ya Faiz!"
        logging.error(f"invoke_kaia error: {e}")
        return f"Kendala teknis: {str(e)}"