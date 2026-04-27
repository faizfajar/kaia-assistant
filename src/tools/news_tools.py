import os
from langchain_core.tools import tool
from tavily import TavilyClient

@tool
def search_news(query: str, search_depth: str = "advanced", topic: str = "general", max_results: int = 5):
    """
    Search for real-time news, tech updates, sports, or political issues.
    
    Args:
        query: The search query string.
        search_depth: 'basic' or 'advanced' (default).
        topic: 'general' or 'news' (optimized for recent events).
        max_results: Number of results to return (default 5).
    """
    api_key = os.getenv("TAVILY_TOKEN")
    if not api_key:
        return "Error: TAVILY_TOKEN not found in environment variables."
    
    client = TavilyClient(api_key=api_key)
    try:
        response = client.search(
            query=query,
            search_depth=search_depth,
            topic=topic,
            max_results=max_results
        )
        
        results = response.get("results", [])
        if not results:
            return f"No news found for: {query}"
        
        formatted_results = []
        for res in results:
            formatted_results.append({
                "title": res.get("title"),
                "url": res.get("url"),
                "content": res.get("content"),
                "published_date": res.get("published_date", "N/A")
            })
            
        return formatted_results
    except Exception as e:
        return f"Tavily Search Error: {str(e)}"
