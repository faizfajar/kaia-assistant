import os
from typing import Literal, Annotated, Sequence
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, BaseMessage
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode

# Internal imports
from src.agent.state import AgentState
from src.agent.prompts import SUPERVISOR_SYSTEM_PROMPT
from src.agent.workers.researcher import researcher_node
from src.agent.workers.secretary import secretary_node
from src.tools import ALL_TOOLS

load_dotenv()

# --- Configuration: Structured Output Schema ---
class RouterConfig(BaseModel):
    """
    Schema for the Supervisor's routing decision. 
    Ensures the LLM selects a valid next node or finishes the cycle.
    """
    next: Literal["Researcher", "Secretary", "DevOps", "News", "FINISH"] = Field(
        description="The next specialist agent to act, or 'FINISH' if the user request is fully satisfied."
    )

# --- LLM Setup ---

llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite-preview",
    google_api_key=os.getenv("GEMINI_API_KEY"),
    temperature=0.1 # Low temperature for consistent routing logic
)

# Bind the RouterConfig schema to the LLM to enforce structured output
structured_llm = llm.with_structured_output(RouterConfig)

# --- Node Definitions ---

def supervisor_node(state: AgentState) -> dict:
    system_message = {"role": "system", "content": SUPERVISOR_SYSTEM_PROMPT}
    
    try:
        decision = structured_llm.invoke([system_message] + state["messages"])
        
        if decision.next == "FINISH":
            last_message = state["messages"][-1]
            
            # If the last message is a ToolMessage or empty, try to synthesize
            if not hasattr(last_message, "content") or len(last_message.content) < 5:
                prompt = "Briefly summarize the action taken for the user in a friendly way."
                # Use a try-except here to catch 503 errors during synthesis
                try:
                    response = llm.invoke(state["messages"] + [HumanMessage(content=prompt)])
                    return {"next": "FINISH", "messages": [response]}
                except:
                    # Fallback: if synthesis fails, just finish
                    return {"next": "FINISH"}
            
            return {"next": "FINISH"}
        
        return {"next": decision.next}
    except Exception as e:
        # If the routing itself fails, we force a finish to prevent loops
        return {"next": "FINISH"}

# Centralized tool node for workers to execute their specific functions
tool_node = ToolNode(ALL_TOOLS)

# --- Routing ---

def router(state: AgentState) -> Literal["Researcher", "Secretary", "FINISH"]:
    """
    Directs the workflow based on the Supervisor's structured decision.
    """
    return state["next"]

def worker_should_continue(state: AgentState) -> Literal["call_tool", "Supervisor"]:
    """
    Conditional edge to handle tool calling logic within workers.
    If the worker generates tool_calls, route to tool_node; otherwise, return to Supervisor.
    """
    last_message = state["messages"][-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "call_tool"
    return "Supervisor"

# --- Graph Construction ---

def build_graph() -> StateGraph:
    """
    Constructs the Multi-Agent Star Topology.
    Supervisor acts as the hub for all communication and delegation.
    """
    workflow = StateGraph(AgentState)

    # 1. Register specialized worker and orchestrator nodes
    workflow.add_node("Supervisor", supervisor_node)
    workflow.add_node("Researcher", researcher_node)
    workflow.add_node("Secretary", secretary_node)
    workflow.add_node("call_tool", tool_node)

    # 2. Define the graph entry point
    workflow.set_entry_point("Supervisor")

    # 3. Define conditional edges for the Supervisor (Orchestration)
    workflow.add_conditional_edges(
        "Supervisor",
        router,
        {
            "Researcher": "Researcher",
            "Secretary": "Secretary",
            "FINISH": END
        }
    )

    # 4. Define edges for Workers (Tool Loop and Feedback)
    # Researcher logic
    workflow.add_conditional_edges(
        "Researcher",
        worker_should_continue,
        {
            "call_tool": "call_tool",
            "Supervisor": "Supervisor"
        }
    )

    # Secretary logic
    workflow.add_conditional_edges(
        "Secretary",
        worker_should_continue,
        {
            "call_tool": "call_tool",
            "Supervisor": "Supervisor"
        }
    )

    # After any tool execution, the graph must return to the Supervisor for review
    workflow.add_edge("call_tool", "Supervisor")

    return workflow.compile()

# Instantiate the compiled graph for use
kaia_graph = build_graph()

# --- Public Interface ---

import logging
from langchain_core.messages import HumanMessage

def invoke_kaia(
    user_input: str,
    chat_history: list
) -> str:
    """
    Robust entry point for the Kaia Assistant.
    Implements message backtracking and fail-safe error handling for production stability.
    """
    # 1. Initialize Graph State
    initial_state: AgentState = {
        "messages": [*chat_history, HumanMessage(content=user_input)],
        "next": "Supervisor"
    }

    try:
        # 2. Execute the LangGraph workflow
        # Note: Ensure the graph is compiled with a checkpointer if persistence is needed
        final_state = kaia_graph.invoke(initial_state)
        messages = final_state.get("messages", [])

        if not messages:
            return "Graph execution returned an empty state. Please verify the Supervisor routing."

        # 3. Message Backtracking Logic
        # We iterate backwards through the history to find the most recent 
        # message that contains actual, displayable string content.
        for msg in reversed(messages):
            # Check if the message has content and is not just a tool-call placeholder
            if hasattr(msg, "content") and isinstance(msg.content, str) and msg.content.strip():
                return msg.content

        # 4. Fallback for successful execution but empty content
        return "I have processed your request, but no text response was generated."

    except Exception as e:
        # 5. Defensive Error Handling for API Spikes (e.g., 503 Overload)
        error_str = str(e).lower()
        logging.error(f"Kaia Runtime Error: {error_str}")

        # Handling specific Gemini API failure modes
        if "503" in error_str or "overloaded" in error_str:
            return "The Gemini engine is currently experiencing high demand (Error 503). Please wait a few seconds and try again."
        
        if "rate_limit" in error_str or "429" in error_str:
            return "We've hit the API rate limit. Let's take a short break before trying again."

        return "I encountered a technical issue while processing your request. Could you please repeat that?"