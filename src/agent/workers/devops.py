import logging
from langchain_core.messages import AIMessage
from langgraph.prebuilt import create_react_agent
from src.agent.prompts import DEVOPS_PROMPT


def get_devops_node(llm, github_tools: list):
    """
    Factory function that creates a DevOps worker node
    with injected MCP GitHub tools.

    Uses create_react_agent for internal ReAct loop (Thought/Action/Observation).
    Extracts only the last meaningful AI message to keep global state clean.
    Always sets active_worker for proper tool routing.
    """
    if not github_tools:
        logging.warning("DevOps node initialized with no GitHub tools.")

    agent = create_react_agent(
        llm,
        tools=github_tools,
        prompt=DEVOPS_PROMPT
    )

    def devops_node(state) -> dict:
        try:
            result = agent.invoke(state)
            all_messages = result.get("messages", [])

            # Extract last meaningful AI response — skip empty content
            last_ai_message = None
            for msg in reversed(all_messages):
                if (
                    isinstance(msg, AIMessage)
                    and msg.content
                    and str(msg.content).strip()
                ):
                    last_ai_message = msg
                    break

            # Fallback if no meaningful AI message found
            if last_ai_message is None:
                last_ai_message = AIMessage(
                    content="Tidak ada data yang ditemukan dari GitHub."
                )

            return {
                "messages": [last_ai_message],
                "active_worker": "DevOps"
            }

        except Exception as e:
            logging.error(f"DevOps node error: {e}")
            return {
                "messages": [AIMessage(content=f"DevOps error: {str(e)}")],
                "active_worker": "DevOps"
            }

    return devops_node