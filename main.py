import re
import logging
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage

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

# Internal tag for Kaia's autonomous long-term memory updates
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

def clean_response(response_text: str) -> str:
    """
    Main pipeline for preparing the final output for the user.
    Normalization -> Internal Tag Removal -> Security Redaction.
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
    Scans the raw LLM output for memory tags and persists them to long-term storage.
    Filters out the [REMEMBER:] prefix before saving to the memory database.
    """
    normalized = get_text_from_response(response_text)
    facts = REMEMBER_PATTERN.findall(normalized)
    
    for fact in facts:
        clean_fact = fact.replace("[REMEMBER:", "").replace("]", "").strip()
        add_fact(clean_fact)
        # Internal log for developer awareness during runtime
        print(f"  Memory Saved: {clean_fact}")

# ── Chat Interface ──────────────────────────────────────────────────────────

def greet_user() -> str:
    """
    Handles session initialization and personalized user greeting.
    """
    memory = load_memory()
    user_name = memory.get("user_name")

    if user_name:
        print(f"\nKaia: Haii {user_name}! Seneng ketemu lagi 😊")
    else:
        user_name = input("Hai! Siapa namamu? → ").strip()
        memory["user_name"] = user_name
        save_memory(memory)
        print(f"\nKaia: Haii {user_name}! Seneng bisa kenalan 😊")

    return user_name

def chat() -> None:
    """
    The main interaction loop. Handles the transition from Monolithic 
    to Multi-Agent (A2A) orchestration.
    """
    user_name = greet_user()
    print("(type 'exit' to quit)\n")

    chat_history = []

    while True:
        try:
            clean_user_label = user_name.replace(":", "").strip()
            user_input = input(f"{clean_user_label}: ").strip()

            if user_input.lower() in ["exit", "quit"]:
                print("Kaia: Oke, sampai ketemu lagi! 👋")
                break

            if not user_input:
                continue

            # ── Multi-Agent Invocation ───────────────────────────────────────
            # The signature is updated for A2A. Internal agents (Secretary)
            # now handle user_name and summary retrieval autonomously.
            raw_reply = invoke_kaia(
                user_input=user_input,
                chat_history=chat_history
            )

            # Internal Persistent memory updates
            extract_and_save_facts(raw_reply)
            
            # External Safe and clean UI response
            kaia_reply = clean_response(raw_reply)

            print(f"\nKaia: {kaia_reply}\n")

            # Maintain session history using standard message objects
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