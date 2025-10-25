"""Web search tool using DuckDuckGo"""

from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

from backend.core.web_utils import clean_ui_artifacts


def duckduckgo_search(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """
    Search the web using DuckDuckGo
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return (default: 5)
    
    Returns:
        List of dictionaries with keys:
            - title: Page title
            - url: Page URL
            - snippet: Short description/snippet
            - search_time: Time taken for search (seconds)
    
    Example:
        results = duckduckgo_search("Python web scraping", max_results=3)
        for result in results:
            print(f"{result['title']}: {result['url']}")
    """
    import time
    
    try:
        from ddgs import DDGS
        
        logger.info(f"Searching DuckDuckGo for: {query}")
        start_time = time.time()
        
        results = []
        with DDGS() as ddgs:
            search_results = ddgs.text(query, max_results=max_results)
            
            for r in search_results:
                results.append({
                    'title': r.get('title', ''),
                    'url': r.get('href', ''),
                    'snippet': r.get('body', '')
                })
        
        search_time = time.time() - start_time
        
        # Добавить время поиска к каждому результату
        for r in results:
            r['search_time'] = search_time
        
        logger.info(f"Found {len(results)} results in {search_time:.2f}s")
        return results
        
    except ImportError:
        logger.error("ddgs library not installed. Run: pip install ddgs")
        return []
    except Exception as e:
        logger.error(f"Search error: {e}")
        return []


def format_search_results(results: List[Dict[str, str]]) -> str:
    """
    Format search results as readable text for LLM
    
    Args:
        results: List of search result dictionaries
    
    Returns:
        Formatted string with numbered results
    """
    if not results:
        return "⚠️ **No results found** - Search returned 0 results. Cannot provide information on this query."
    
    search_time = results[0].get('search_time', 0) if results else 0
    
    formatted = f"🔍 **Search Results** (Found {len(results)} results in {search_time:.2f}s):\n\n"
    
    for i, result in enumerate(results, 1):
        title = result.get('title', 'No title')
        url = result.get('url', '')
        snippet = result.get('snippet', 'No description')
        
        formatted += f"{i}. **{title}**\n"
        formatted += f"   📎 {url}\n"
        formatted += f"   📝 {snippet[:200]}{'...' if len(snippet) > 200 else ''}\n\n"
    
    return clean_ui_artifacts(formatted)
    
    search_time = results[0].get('search_time', 0) if results else 0
    
    formatted = f"🔍 **Search Results** (Found {len(results)} results in {search_time:.2f}s):\n\n"
    
    for i, result in enumerate(results, 1):
        title = result.get('title', 'No title')
        url = result.get('url', '')
        snippet = result.get('snippet', 'No description')
        
        formatted += f"{i}. **{title}**\n"
        formatted += f"   📎 {url}\n"
        formatted += f"   📝 {snippet[:200]}{'...' if len(snippet) > 200 else ''}\n\n"
    
    return formatted
