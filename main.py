import re
from src.agent.graph import invoke_kaia
from src.agent.memory import (
    load_memory, save_memory,
    add_fact, get_memory_summary
)

# ── Constants ──────────────────────────────────────────────────────────────────

REMEMBER_PATTERN = re.compile(r'\[REMEMBER:\s*(.+?)\]', re.IGNORECASE)


# ── Memory Helpers ─────────────────────────────────────────────────────────────

def get_text_from_response(content) -> str:
    """
    Normalize LLM response content to plain string.
    
    Different models return content in different formats:
    - Most models: plain string
    - Some models: list of content blocks (dicts or objects)
    
    This helper ensures consistent string output regardless of model used,
    making the codebase model-agnostic.
    """
    if isinstance(content, str):
        return content
    
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                parts.append(block.get("text", ""))
            else:
                parts.append(str(block))
        return " ".join(filter(None, parts))
    
    return str(content)


def extract_and_save_facts(response_text: str) -> None:
    """
    Parse [REMEMBER: fact] tags from Kaia's response
    and persist each extracted fact to long-term memory.
    """
    # Normalize dulu sebelum diproses — model-agnostic
    normalized = get_text_from_response(response_text)
    facts = REMEMBER_PATTERN.findall(normalized)
    for fact in facts:
        add_fact(fact.strip())
        print(f"  [Memory saved: {fact.strip()}]")


def clean_response(response_text: str) -> str:
    """Remove [REMEMBER: ...] tags before displaying response to user."""
    normalized = get_text_from_response(response_text)
    return REMEMBER_PATTERN.sub("", normalized).strip()


def clean_response(response_text: str) -> str:
    """Remove [REMEMBER: ...] tags before displaying response to user."""
    return REMEMBER_PATTERN.sub("", response_text).strip()


# ── Greeting ───────────────────────────────────────────────────────────────────

def greet_user() -> str:
    """
    Handle greeting flow based on existing memory.
    Returns the user's name.
    """
    memory = load_memory()

    if memory["user_name"]:
        user_name = memory["user_name"]
        last_seen = memory["last_seen"]
        print(f"\nKaia: Haii {user_name}! Seneng ketemu lagi 😊")
        if last_seen:
            print(f"       Terakhir kita ngobrol {last_seen}.")
    else:
        user_name = input("Hai! Siapa namamu? → ").strip()
        memory["user_name"] = user_name
        save_memory(memory)
        print(f"\nKaia: Haii {user_name}! Seneng bisa kenalan 😊")
        print(f"       Ada yang bisa aku bantu, atau mau ngobrol aja?")

    return user_name


# ── Main Chat Loop ─────────────────────────────────────────────────────────────

def chat() -> None:
    """
    Main conversation loop with tool calling support.
    Delegates LLM invocation to graph.py (orchestration layer).
    """
    user_name = greet_user()
    print("(ketik 'exit' untuk keluar)\n")

    chat_history = []

    while True:
        user_input = input(f"{user_name}: ").strip()

        if user_input.lower() == "exit":
            print("Kaia: Oke, sampai ketemu lagi! Take care ya 👋")
            break

        if not user_input:
            continue

        raw_reply = invoke_kaia(
            user_input=user_input,
            user_name=user_name,
            memory_summary=get_memory_summary(),
            chat_history=chat_history
        )

        extract_and_save_facts(raw_reply)
        kaia_reply = clean_response(raw_reply)

        print(f"\nKaia: {kaia_reply}\n")

        from langchain_core.messages import HumanMessage, AIMessage
        chat_history.append(HumanMessage(content=user_input))
        chat_history.append(AIMessage(content=kaia_reply))


if __name__ == "__main__":
    chat()