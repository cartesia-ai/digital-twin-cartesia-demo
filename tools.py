from pathlib import Path
from typing import Annotated, Optional

from loguru import logger
from tavily import AsyncTavilyClient
from pypdf import PdfReader

from line.llm_agent import loopback_tool
from line.llm_agent import ToolEnv

RESUME_PDF = Path(__file__).parent / "profile.pdf"


@loopback_tool
async def read_resume(ctx: ToolEnv):
    """Read resume PDF and return its full text content."""
    if not RESUME_PDF.exists():
        return "Resume PDF not found."

    reader = PdfReader(RESUME_PDF)
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages).strip()


EXTRACT_MAX_CHARS = 3000

class TavilyTools:
    """Holds a single AsyncTavilyClient so the underlying httpx session and
    connection pool are reused across tool calls."""

    def __init__(self, api_key: str):
        self._client = AsyncTavilyClient(
            api_key=api_key, client_source="cartesia-line-agent")

    @loopback_tool
    async def web_search(
        self,
        ctx: ToolEnv,
        query: Annotated[
            str,
            "The search query. Be specific and include key terms.",
        ],
        time_range: Annotated[
            Optional[str],
            "Optional time range filter. Use 'day', 'week', 'month', or 'year' for recent topics. ",
        ] = None,
    ) -> str:
        """Search the web for current information.
        Use when you need up-to-date facts, news, or any information that requires factual accuracy."""
        logger.info(f"Performing Tavily web search: '{query}'")

        try:
            search_kwargs: dict = {"query": query,
                                   "search_depth": "fast", "max_results": 5}
            if time_range is not None:
                search_kwargs["time_range"] = time_range
            response = await self._client.search(**search_kwargs)

            results = response.get("results", [])
            if not results:
                return "No relevant information found."

            content_parts = [f"Search Results for: '{query}'\n"]
            for i, result in enumerate(results):
                score = result.get("score", 0)
                content_parts.append(
                    f"\n--- Source {i + 1}: {result['title']} (relevance: {score:.2f}) ---\n"
                )
                if result.get("content"):
                    content_parts.append(f"{result['content']}\n")
                content_parts.append(f"URL: {result['url']}\n")

            response_time = response.get("response_time", 0)
            logger.info(
                f"Search completed: {len(results)} sources found in {response_time:.2f}s")
            return "".join(content_parts)

        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            return f"Web search failed: {e}"

    @loopback_tool
    async def web_extract(
        self,
        ctx: ToolEnv,
        url: Annotated[
            str,
            "The URL to extract content from.",
        ],
    ) -> str:
        """Extract the full content of a webpage given its URL.
        Use when you need detailed information from a specific page found via web_search."""
        logger.info(f"Extracting content from: '{url}'")

        try:
            response = await self._client.extract(urls=[url])

            results = response.get("results", [])
            if not results:
                failed = response.get("failed_results", [])
                if failed:
                    return f"Extraction failed for {url}: {failed[0].get('error', 'unknown error')}"
                return "No content could be extracted from that URL."

            extracted = results[0]
            raw_content = extracted.get("raw_content", "")
            if not raw_content:
                return "The page was reached but no readable content was found."

            if len(raw_content) > EXTRACT_MAX_CHARS:
                raw_content = raw_content[:EXTRACT_MAX_CHARS] + \
                    "\n\n[Content truncated]"

            logger.info(
                f"Extraction completed: {len(raw_content)} characters from {url}")
            return f"Extracted content from {url}:\n\n{raw_content}"

        except Exception as e:
            logger.error(f"Tavily extract failed: {e}")
            return f"Content extraction failed: {e}"


