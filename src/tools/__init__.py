from src.tools.secretary_tools import save_note, get_notes, delete_note, get_current_datetime
from src.tools.rag_tool import search_knowledge, add_document_to_db

# Central registry of all available tools.
# To add a new tool: import it above and add to this list.
ALL_TOOLS = [
    get_current_datetime,
    save_note,
    get_notes,
    delete_note,
    search_knowledge,
    add_document_to_db
]