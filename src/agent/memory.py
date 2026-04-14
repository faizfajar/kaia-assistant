import json
import os
from datetime import datetime

# Path to the persistent memory file
MEMORY_PATH = "data/memory.json"

# Default memory structure when no memory file exists
DEFAULT_MEMORY: dict = {
    "user_name": "",
    "facts": [],
    "last_seen": ""
}


def load_memory() -> dict:
    """
    Load memory from the JSON file.
    Returns default memory structure if file does not exist.
    """
    if not os.path.exists(MEMORY_PATH):
        return DEFAULT_MEMORY.copy()

    with open(MEMORY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_memory(memory: dict) -> None:
    """
    Persist memory to the JSON file.
    Automatically updates the last_seen timestamp before saving.
    """
    memory["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    os.makedirs(os.path.dirname(MEMORY_PATH), exist_ok=True)

    with open(MEMORY_PATH, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=2, ensure_ascii=False)


def add_fact(fact: str) -> None:
    """
    Add a new fact about the user to long-term memory.
    Skips duplicate facts to avoid redundancy.
    """
    memory = load_memory()

    # Normalize for duplicate check (case-insensitive)
    existing_facts_lower = [f.lower() for f in memory["facts"]]

    if fact.lower() not in existing_facts_lower:
        memory["facts"].append(fact)
        save_memory(memory)


def get_memory_summary() -> str:
    """
    Convert stored memory into a readable summary string.
    This summary is injected into Kaia's system prompt.
    """
    memory = load_memory()

    has_no_memory = not memory["user_name"] and not memory["facts"]
    if has_no_memory:
        return "No information stored about this user yet."

    lines = []

    if memory["user_name"]:
        lines.append(f"- Name: {memory['user_name']}")

    if memory["last_seen"]:
        lines.append(f"- Last conversation: {memory['last_seen']}")

    if memory["facts"]:
        lines.append("- Known facts:")
        for fact in memory["facts"]:
            lines.append(f"    • {fact}")

    return "\n".join(lines)