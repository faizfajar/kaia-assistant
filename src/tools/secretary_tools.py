import json
import os
from datetime import datetime
from langchain_core.tools import tool

NOTES_PATH = "data/notes.json"

def _load_notes() -> dict:
    """Load notes from JSON file with error handling."""
    if not os.path.exists(NOTES_PATH):
        return {"notes": []}
    try:
        with open(NOTES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {"notes": []}

def _save_notes(data: dict) -> None:
    """Persist notes to JSON file."""
    # Ensure directory exists
    os.makedirs(os.path.dirname(NOTES_PATH), exist_ok=True)
    with open(NOTES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

@tool
def get_current_datetime() -> str:
    """
    Get the current date and time.
    Use this when the user mentions relative time like 'tomorrow', 
    'next week', or 'tonight' to resolve the exact date.
    """
    return f"Current date and time is: {datetime.now().strftime('%A, %Y-%m-%d %H:%M')}"

@tool
def save_note(content: str) -> str:
    """
    Save a note or reminder for the user.
    Use this when the user asks to save, note down, remind, 
    or remember something specific.
    """
    data = _load_notes()

    # Robust ID generation: find the maximum current ID and add 1
    new_id = max([n["id"] for n in data["notes"]], default=0) + 1

    note = {
        "id": new_id,
        "content": content,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }

    data["notes"].append(note)
    _save_notes(data)

    return f"Note saved successfully with ID {new_id}: '{content}'"

@tool
def get_notes() -> str:
    """
    Retrieve all saved notes for the user.
    Use this when the user asks to see, show, list, or retrieve their notes.
    """
    data = _load_notes()

    if not data["notes"]:
        return "You don't have any notes saved yet."

    lines = ["### Your Saved Notes:"]
    for note in data["notes"]:
        lines.append(f"- **[{note['id']}]** {note['content']} *(Saved: {note['created_at']})*")

    return "\n".join(lines)

@tool
def delete_note(note_id: int) -> str:
    """
    Delete a specific note by its ID.
    """
    data = _load_notes()
    
    # Force casting to int to prevent string vs int mismatch
    try:
        target_id = int(note_id)
    except:
        return "Error: Invalid ID format."

    original_count = len(data["notes"])
    # Filter out the note
    data["notes"] = [n for n in data["notes"] if int(n["id"]) != target_id]

    if len(data["notes"]) == original_count:
        return f"Operation failed: Note with ID {target_id} not found."

    _save_notes(data)
    return f"Success: Note {target_id} has been deleted."