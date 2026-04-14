import json
import os
from datetime import datetime
from langchain_core.tools import tool

NOTES_PATH = "data/notes.json"


def _load_notes() -> dict:
    """Load notes from JSON file."""
    if not os.path.exists(NOTES_PATH):
        return {"notes": []}
    with open(NOTES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_notes(data: dict) -> None:
    """Persist notes to JSON file."""
    with open(NOTES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


@tool
def save_note(content: str) -> str:
    """
    Save a note or reminder for the user.
    Use this when the user asks to save, note down, remind,
    or remember something specific (e.g. tasks, schedules, ideas).

    Args:
        content: The note content to save.
    """
    data = _load_notes()

    note = {
        "id": len(data["notes"]) + 1,
        "content": content,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }

    data["notes"].append(note)
    _save_notes(data)

    return f"Note saved successfully: '{content}'"


@tool
def get_notes() -> str:
    """
    Retrieve all saved notes for the user.
    Use this when the user asks to see, show, list,
    or retrieve their notes or reminders.
    """
    data = _load_notes()

    if not data["notes"]:
        return "No notes found."

    lines = ["Here are your saved notes:"]
    for note in data["notes"]:
        lines.append(f"  [{note['id']}] {note['content']} (saved: {note['created_at']})")

    return "\n".join(lines)


@tool
def delete_note(note_id: int) -> str:
    """
    Delete a specific note by its ID.
    Use this when the user asks to delete or remove a specific note.

    Args:
        note_id: The ID of the note to delete.
    """
    data = _load_notes()

    original_count = len(data["notes"])
    data["notes"] = [n for n in data["notes"] if n["id"] != note_id]

    if len(data["notes"]) == original_count:
        return f"Note with ID {note_id} not found."

    _save_notes(data)
    return f"Note {note_id} deleted successfully."