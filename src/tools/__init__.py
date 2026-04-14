from src.tools.datetime_tool import get_current_datetime
from src.tools.notes_tool import save_note, get_notes, delete_note

# Central registry of all available tools.
# To add a new tool: import it above and add to this list.
ALL_TOOLS = [
    get_current_datetime,
    save_note,
    get_notes,
    delete_note,
]