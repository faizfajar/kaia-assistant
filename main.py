import re
import logging
from dotenv import load_dotenv

# Load environment variables at the absolute start
load_dotenv()

from src.agent.graph import invoke_kaia
from src.agent.memory import (
    load_memory, save_memory,
    add_fact, get_memory_summary
)

# ── Pattern Configurations ───────────────────────────────────────────────────

# Specific pattern for Google/Gemini API Keys
API_KEY_PATTERN = re.compile(r"AIza[0-9A-Za-z-_]{35}")

# Generic pattern for secrets, passwords, or tokens found in text
SECRET_PATTERN = re.compile(r"(?i)(api_key|secret|password|token)\s*[:=]\s*['\"]?[0-9a-zA-Z-_]{16,}['\"]?")

# Internal tag for Kaia's long-term memory updates
REMEMBER_PATTERN = re.compile(r"\[REMEMBER:.*?\]", re.DOTALL)

# ── Security & Normalization Helpers ─────────────────────────────────────────

def security_filter(text: str) -> str:
    """
    Acts as an output guardrail by redacting sensitive strings or API keys.
    Prevents accidental leakage of credentials to the user interface.
    """
    filtered = text
    
    # Redact identified Gemini API keys
    if API_KEY_PATTERN.search(filtered):
        filtered = API_KEY_PATTERN.sub("[SENSITIVE_API_KEY_REDACTED]", filtered)
    
    # Redact generic secret assignments
    if SECRET_PATTERN.search(filtered):
        filtered = SECRET_PATTERN.sub(r"\1: [REDACTED_SECRET]", filtered)
        
    return filtered

def get_text_from_response(content) -> str:
    """
    Normalizes complex LLM return objects into a standard string.
    Ensures compatibility across different model output formats.
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

def clean_response(response_text) -> str:
    """
    Main pipeline for preparing the final output for the user.
    Removes internal memory tags and applies security filters.
    """
    try:
        # Normalize the raw content
        normalized = get_text_from_response(response_text)
        
        # Remove [REMEMBER: ...] tags so they are invisible to the user
        cleaned = REMEMBER_PATTERN.sub("", normalized).strip()
        
        # Apply the final security guardrail
        return security_filter(cleaned)
        
    except Exception as e:
        logging.error(f"Failed to process response: {e}")
        return "I encountered a technical issue while processing the response."

def extract_and_save_facts(response_text: str) -> None:
    """
    Scans the raw LLM output for memory tags and persists them.
    Note: We store the raw fact in memory but redact it in the UI.
    """
    normalized = get_text_from_response(response_text)
    facts = REMEMBER_PATTERN.findall(normalized)
    
    for fact in facts:
        # Strip the tags before saving to the JSON/Vector database
        clean_fact = fact.replace("[REMEMBER:", "").replace("]", "").strip()
        add_fact(clean_fact)
        # Log to terminal for developer awareness
        print(f"  Memory Saved: {clean_fact}")

# ── Chat Interface ──────────────────────────────────────────────────────────

def greet_user() -> str:
    """
    Loads session memory and provides a personalized greeting.
    """
    memory = load_memory()
    user_name = memory.get("user_name")

    if user_name:
        last_seen = memory.get("last_seen", "recently")
        print(f"\nKaia: Haii {user_name}! Seneng ketemu lagi 😊")
        print(f"       Terakhir kita ngobrol {last_seen}.")
    else:
        user_name = input("Hai! Siapa namamu? → ").strip()
        memory["user_name"] = user_name
        save_memory(memory)
        print(f"\nKaia: Haii {user_name}! Seneng bisa kenalan 😊")
        print(f"       Ada yang bisa aku bantu?")

    return user_name

def chat() -> None:
    """
    The main conversation loop managing the graph execution and history.
    """
    user_name = greet_user()
    print("(type 'exit' to quit)\n")

    chat_history = []

    while True:
        try:
            user_input = input(f"{user_name}: ").strip()

            if user_input.lower() in ["exit", "quit"]:
                print("Kaia: Oke, sampai ketemu lagi! Take care ya 👋")
                break

            if not user_input:
                continue

            # Execute the LangGraph workflow
            raw_reply = invoke_kaia(
                user_input=user_input,
                user_name=user_name,
                memory_summary=get_memory_summary(),
                chat_history=chat_history
            )

            # Internal processing (Memory updates)
            extract_and_save_facts(raw_reply)
            
            # External processing (Safe UI output)
            kaia_reply = clean_response(raw_reply)

            print(f"\nKaia: {kaia_reply}\n")

            # Maintain history for conversation context
            from langchain_core.messages import HumanMessage, AIMessage
            chat_history.append(HumanMessage(content=user_input))
            chat_history.append(AIMessage(content=kaia_reply))
            
        except KeyboardInterrupt:
            print("\nKaia: System interrupted. Goodbye!")
            break
        except Exception as e:
            logging.error(f"Runtime Error: {e}")
            print("Kaia: Maaf, otaku lagi sedikit panas. Bisa diulang pertanyaannya?")

if __name__ == "__main__":
    chat()