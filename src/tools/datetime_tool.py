from datetime import datetime
from langchain_core.tools import tool


@tool
def get_current_datetime() -> str:
    """
    Get the current date and time.
    Use this when the user asks about today's date, current time,
    or anything related to 'now', 'today', 'what time is it', etc.
    """
    now = datetime.now()
    return now.strftime("Today is %A, %d %B %Y. Current time is %H:%M.")