import os, textwrap
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright


from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import Swarm
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.ui import Console

# Use ONE of these model clients ↓ depending on your setup.
from autogen_ext.models.openai import OpenAIChatCompletionClient, AzureOpenAIChatCompletionClient

# ---------- Choose your model client ----------
def build_model_client():
    if os.getenv("AZURE_OPENAI_ENDPOINT"):
        return AzureOpenAIChatCompletionClient(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
    return OpenAIChatCompletionClient(model=os.getenv("OPENAI_MODEL", "gpt-4o"))


# ---------- Simple web "tool" the Researcher can call ----------
def fetch_url_summary(url: str) -> str:
    """Fetch a page (JS-rendered if needed) and summarize it."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; ARM Mac OS X 14_5)"
                "AppleWebKit/537.36 (KHTML, like Gecko)"
                "Chrome/128.0.6613.119 Safari/537.36"
            )
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

# ---------- Define the agents ----------
def build_team():
    model_client = build_model_client()

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

    termination = TextMentionTermination("TERMINATE")
    return Swarm([manager, researcher, tester], termination_condition=termination), model_client

async def run_pipeline(task: str) -> str:
    team, model_client = build_team()
    output_parts = []
    async for event in team.run_stream(task=task):
        content = getattr(event, "content", None)
        if isinstance(content, str) and content.strip():
            output_parts.append(content)
    await model_client.close()
    return "\n".join(output_parts) if output_parts else "(no content)"
