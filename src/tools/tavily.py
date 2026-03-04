from typing import Dict, Any, List
from tavily import AsyncTavilyClient
from src.core.config import settings
from src.core.tool_manager import tool

@tool
async def web_search(query: str) -> List[Dict[str, Any]]:
    """Performs a web search using Tavily and returns the top 5 most relevant results."""
    # Check if API key is configured
    if not settings.TAVILY_API_KEY:
        raise ValueError("TAVILY_API_KEY is not set in the configuration.")

    # Initialize the async client
    client = AsyncTavilyClient(api_key=settings.TAVILY_API_KEY)
    
    # Perform the search, limiting to 5 results to avoid saturating context
    try:
        response = await client.search(
            query=query,
            search_depth=settings.TAVILY_SEARCH_DEPTH,
            max_results=settings.TAVILY_MAX_RESULTS,
        )
        
        # Extract and return the results
        # Tavily response usually contains a 'results' list with dicts containing 'title', 'url', 'content'
        return response.get("results", [])
    except Exception as e:
        # Re-raise with a clear message or handle depending on JotaOrchestrator's error strategy
        raise RuntimeError(f"Tavily web search failed: {str(e)}")
