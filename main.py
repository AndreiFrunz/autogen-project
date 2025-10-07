# main.py
import os, asyncio, textwrap, requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import Swarm
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.ui import Console

# Use ONE of these model clients ↓ depending on your setup.
from autogen_ext.models.openai import OpenAIChatCompletionClient, AzureOpenAIChatCompletionClient

# ---------- Choose your model client ----------

USE_AZURE = bool(os.getenv("AZURE_OPENAI_ENDPOINT"))

if USE_AZURE:
    # API-key mode; for AAD see cookbook (token provider) instead. :contentReference[oaicite:7]{index=7}
    model_client = AzureOpenAIChatCompletionClient(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
        api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        # Suggest disabling parallel tool calls for handoffs in Swarm (optional): parallel_tool_calls=False
    )
else:
    model_client = OpenAIChatCompletionClient(
        model="gpt-4o-mini",  # pick a chat/completions model you have access to
        # api_key pulled from OPENAI_API_KEY env var automatically
    )

# ---------- Simple web "tool" the Researcher can call ----------

# def fetch_url_summary(url: str) -> str:
#     """Fetch a URL and return a short summary (title + first ~600 chars)."""
#     headers = {
#         "User-Agent": (
#             "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
#             "AppleWebKit/537.36 (KHTML, like Gecko) "
#             "Chrome/128.0.0.0 Safari/537.36"
#         ),
#         "Accept-Language": "en-US,en;q=0.9",
#         "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
#         "Referer": "https://www.google.com/",
#         "Connection": "keep-alive",
#     }
#     resp = requests.get(url,headers=headers, timeout=20)
#     resp.raise_for_status()
#     soup = BeautifulSoup(resp.text, "html.parser")
#     print(" >>>>>>>> soup <<<<<<<<" )
#     print("soup", soup)
#     print(" >>>>>>> soup <<<<<<<<" )
#     title = (soup.title.string.strip() if soup.title and soup.title.string else url)
#     # Basic text scrape (very naive, good enough for demo)
#     text = " ".join(s.strip() for s in soup.get_text(" ").split())
#     snippet = text[:600]
#     return f"TITLE: {title}\nURL: {url}\nSNIPPET: {snippet}"





def fetch_url_summary(url: str) -> str:
    """Fetch a page (JS-rendered if needed) and summarize it."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; ARM Mac OS X 14_5)"
                "AppleWebKit/537.36 (KHTML, like Gecko)"
                "Chrome/128.0.6613.119 Safari/537.36"
            )
        )
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        html = page.content()
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

# ---------- Define the agents ----------

manager = AssistantAgent(
    name="manager",
    model_client=model_client,
    handoffs=["researcher", "tester"],  # who manager can hand off to
    system_message=textwrap.dedent("""
        You are the Manager. Orchestrate the workflow:
        1) If a URL/topic is given, HAND OFF to 'researcher' to gather facts using tools.
        2) Then HAND OFF to 'tester' to produce simple Playwright-style tests (JS).
        3) When done, summarize the final outcome for the user and add 'TERMINATE'.
        Be brief and structured.
    """).strip()
)

researcher = AssistantAgent(
    name="researcher",
    model_client=model_client,
    handoffs=["tester", "manager"],
    tools=[fetch_url_summary],
    system_message=textwrap.dedent("""
        You are the Researcher. If given a URL, call fetch_url_summary(url).
        Present 3-5 concise bullet points with key observations suitable for testing.
        After you present findings, HAND OFF to 'tester'.
    """).strip()
)

tester = AssistantAgent(
    name="tester",
    model_client=model_client,
    handoffs=["manager"],
    system_message=textwrap.dedent("""
        You are the Test Writer. Using the Researcher's notes, generate:
        - 1–3 Playwright JS tests that validate basic navigation/links/text.
        - Keep tests minimal and runnable. Do not execute them.
        When ready, HAND OFF to 'manager'.
    """).strip()
)

# Stop when the manager prints TERMINATE.
termination = TextMentionTermination("TERMINATE")
team = Swarm([manager, researcher, tester], termination_condition=termination)  # :contentReference[oaicite:8]{index=8}

async def run(task: str) -> None:
    # Stream the conversation to the console.
    await Console(team.run_stream(task=task))
    await model_client.close()

if __name__ == "__main__":
    # Example task:
    # - Try with a real website you own/are allowed to crawl, or replace with a static URL.
    asyncio.run(run("Analyze https://www.bancatransilvania.ro/credite/calculatorul-de-rate and write Playwright tests to test if there are the 'Simulator de credit' title exist in page."))
