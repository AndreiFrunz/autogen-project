from typing import Iterable, Optional

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from typing import Optional, Iterable
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from typing import Optional, Iterable
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

def clean_html_with_playwright(
    *,
    url: Optional[str] = None,
    html: Optional[str] = None,
    allowed_attrs: Iterable[str] = ("class", "id", "role"),
    preserve_whitespace_tags: Iterable[str] = ("pre", "code", "kbd", "samp", "textarea"),
    preserve_semantic_tags: bool = True,
    preserve_custom_tags: Optional[Iterable[str]] = None,
    drop_empty: bool = True,
    headless: bool = False,
    timeout_ms: int = 30000,
) -> str:
    """
    Produce a compact HTML snapshot that keeps structure, class/id/role/data/aria, and text.

    Parameters:
      url or html: one must be provided.
      allowed_attrs: attributes to preserve (default: class, id, role).
      preserve_whitespace_tags: tags whose text whitespace is preserved.
      preserve_semantic_tags: if True, semantic tags are preserved even if empty.
      preserve_custom_tags: additional tag names to preserve even if empty.
      drop_empty: remove elements with no content or useful attributes.
      headless: run browser in headless mode.
      timeout_ms: timeout for page load.

    Returns:
      Cleaned HTML string.
    """
    if (url is None) == (html is None):
        raise ValueError("Provide exactly one of `url` or `html`.")

    js_cleaner = """
    (opts) => {
      const allowed = new Set((opts.allowed_attrs || ['class','id','role']).map(s => String(s).toLowerCase()));
      const preserve = new Set((opts.preserve_whitespace_tags || ['pre','code','kbd','samp','textarea']).map(s => String(s).toLowerCase()));
      const semanticTags = new Set([
        'article', 'section', 'nav', 'aside', 'main',
        'header', 'footer', 'figure', 'figcaption',
        'mark', 'time'
      ]);
      const customTags = new Set((opts.preserve_custom_tags || []).map(s => String(s).toLowerCase()));

      const root = document.body.cloneNode(true);

      const shouldStripWholeTag = (el) => {
        const t = el.tagName.toLowerCase();
        return ['script','style','noscript','template','iframe','object','embed'].includes(t);
      };

      const toRemove = [];
      const walker = document.createTreeWalker(
        root,
        NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT | NodeFilter.SHOW_COMMENT
      );

      while (walker.nextNode()) {
        const node = walker.currentNode;

        if (node.nodeType === Node.COMMENT_NODE) {
          toRemove.push(node);
          continue;
        }

        if (node.nodeType === Node.ELEMENT_NODE) {
          const el = node;

          if (shouldStripWholeTag(el)) {
            toRemove.push(el);
            continue;
          }

          for (const name of Array.from(el.getAttributeNames())) {
            const lower = name.toLowerCase();
            if (
              allowed.has(lower) ||
              lower.startsWith("data-") ||
              lower.startsWith("aria-")
            ) {
              continue;
            }
            el.removeAttribute(name);
          }

          if (el.hasAttribute('class') && !el.getAttribute('class').trim()) el.removeAttribute('class');
          if (el.hasAttribute('id') && !el.getAttribute('id').trim()) el.removeAttribute('id');

        } else if (node.nodeType === Node.TEXT_NODE) {
          const parent = node.parentElement;
          const tag = parent ? parent.tagName.toLowerCase() : '';
          if (!preserve.has(tag)) {
            node.nodeValue = node.nodeValue.replace(/\\s+/g, ' ');
          }
        }
      }

      for (const n of toRemove) n.remove();

      if (opts.drop_empty) {
        const prunable = [];
        for (const el of root.querySelectorAll('*')) {
          const tag = el.tagName.toLowerCase();
          const isSemantic = opts.preserve_semantic_tags && semanticTags.has(tag);
          const isCustom = customTags.has(tag);
          const hasUsefulAttr = ['id', 'class', 'role'].some(attr => el.hasAttribute(attr));
          const hasText = (el.textContent || '').trim().length > 0;
          const hasChildElements = el.children.length > 0;

          if (!isSemantic && !isCustom && !hasUsefulAttr && !hasText && !hasChildElements) {
            prunable.push(el);
          }
        }
        for (const el of prunable) el.remove();
      }

      const container = document.createElement('div');
      container.appendChild(root);
      return container.innerHTML
        .replace(/>\\s+</g, '><')
        .replace(/\\s{2,}/g, ' ');
    }
    """

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/128.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()

        try:
            if url is not None:
                page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            else:
                page.set_content(html, wait_until="domcontentloaded")
        except PlaywrightTimeoutError:
            page.wait_for_load_state("domcontentloaded", timeout=5000)

        cleaned = page.evaluate(
            js_cleaner,
            {
                "allowed_attrs": list(allowed_attrs),
                "preserve_whitespace_tags": list(preserve_whitespace_tags),
                "drop_empty": bool(drop_empty),
                "preserve_semantic_tags": bool(preserve_semantic_tags),
                "preserve_custom_tags": list(preserve_custom_tags or []),
            },
        )

        browser.close()
        return cleaned

# # ---------- Simple web "tool" the Researcher can call to return the text content of page ----------
def fetch_url_summary(url: str) -> str:
    """Fetch a page (JS-rendered if needed) and summarize it."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; ARM Mac OS X 14_5)"
                "AppleWebKit/537.36 (KHTML, like Gecko)"
                "Chrome/128.0.6613.119 Safari/537.36"
            ),
            locale="ro-RO",
            viewport={"width": 1280, "height": 800},
            java_script_enabled=True,
        )
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        # html = page.content()
        title = page.title()
        text = page.inner_text("body")
        browser.close()
    # Extract html here
    # soup = BeautifulSoup(html, "html.parser")
    snippet = " ".join(text.split())
    # print(">>>>> snippet <<<<<")
    # print(soup)
    # print(">>>>> snippet <<<<<")
    return f"TITLE: {title}\nURL: {url}\nSNIPPET: {snippet}"
    # return f"Url html's: {soup}"
