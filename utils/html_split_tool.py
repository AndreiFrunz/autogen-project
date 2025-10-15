import asyncio
from typing import List, Dict, Any, Iterable, Tuple, Optional

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup, Comment
from langchain_text_splitters import (
    HTMLSemanticPreservingSplitter,
    HTMLHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

HEADERS: List[Tuple[str, str]] = [
    ("h1", "Header 1"),
    ("h2", "Header 2"),
    ("h3", "Header 3"),
    ("h4", "Header 4"),
]

async def get_html_and_chunks(
    url: str,
    *,
    strategy: str = "semantic",                      # "semantic" | "header"
    chunk_overlap: int = 150,
    preserve_elements: Optional[Iterable[str]] = ("table","thead","tbody","ul","ol","pre","code"),
    remove_tags: Optional[Iterable[str]] = ("script","style","noscript"),
    wait_until: str = "domcontentloaded",            # or "networkidle"
    timeout_ms: int = 45000,
    user_agent: Optional[str] = None,
    extra_headers: Optional[Dict[str, str]] = None,
    wait_selector: Optional[str] = None,             # e.g. "#onetrust-accept-btn-handler" (if you want to ensure cookies banner is present before snapshot)
) -> Dict[str, Any]:
    """
    Fetch a page's HTML with Playwright, clean it, split it with LangChain, and return
    a compact payload suitable for an AI agent.

    Returns:
      {
        "url": str,
        "html": str,  # cleaned HTML
        "dom_chunks": [  # structure-aware chunks for LLMs
            {"text": str, "headers": [str,...], "scope_hint": str},
            ...
        ]
      }
    """
    # 1) Navigate & snapshot DOM
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context_args = {}
        if user_agent:
            context_args["user_agent"] = user_agent
        if extra_headers:
            context_args["extra_http_headers"] = extra_headers
        context = await browser.new_context(**context_args)
        page = await context.new_page()

        try:
            await page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            if wait_selector:
                # Optional: ensure a particular element is present before snapshotting
                await page.wait_for_selector(wait_selector, timeout=timeout_ms)
            raw_html = await page.content()
        finally:
            await context.close()
            await browser.close()

    # 2) Clean HTML (drop noise & comments; keep structure)
    soup = BeautifulSoup(raw_html, "lxml")

    # Remove comments
    for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
        c.extract()

    # Remove noisy tags (scripts/styles) while preserving the rest of the structure
    if remove_tags:
        for tag in remove_tags:
            for el in soup.find_all(tag):
                el.decompose()

    cleaned_html = str(soup)

    # 3) Split HTML into structure-aware chunks for better locator mining
    if strategy == "semantic":
        splitter = HTMLSemanticPreservingSplitter(
            headers_to_split_on=HEADERS,
            chunk_overlap=chunk_overlap,
            elements_to_preserve=list(preserve_elements or ()),
        )
        docs = splitter.split_text(cleaned_html)
    else:
        header_splitter = HTMLHeaderTextSplitter(headers_to_split_on=HEADERS, return_each_element=False)
        docs = header_splitter.split_text(cleaned_html)
        # Keep chunks reasonable in size
        rc = RecursiveCharacterTextSplitter( chunk_overlap=chunk_overlap)
        docs = rc.split_documents(docs)

    # 4) Normalize to a compact, LLM-friendly structure
    dom_chunks: List[Dict[str, Any]] = []
    for d in docs:
        headers = [
            d.metadata.get("Header 1"),
            d.metadata.get("Header 2"),
            d.metadata.get("Header 3"),
            d.metadata.get("Header 4"),
        ]
        headers = [h for h in headers if h]
        dom_chunks.append({
            "text": d.page_content.strip(),
            "headers": headers,
            "scope_hint": " > ".join(headers) if headers else ""
        })

    return {
        "url": url,
        "html": cleaned_html,
        "dom_chunks": dom_chunks,
    }

# --- Optional convenience sync wrapper (use ONLY if you're NOT already inside an event loop) ---
# def get_html_and_chunks_sync(*args, **kwargs):
#     return asyncio.run(get_html_and_chunks(*args, **kwargs))
