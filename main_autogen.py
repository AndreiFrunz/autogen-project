import os, textwrap
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import Swarm
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.ui import Console
from helper import clean_html_with_playwright

# Use ONE of these model clients ↓ depending on your setup.
from autogen_ext.models.openai import OpenAIChatCompletionClient, AzureOpenAIChatCompletionClient

# ---------- Choose your model client ----------
def build_model_client():
    if os.getenv("AZURE_OPENAI_ENDPOINT"):
        return AzureOpenAIChatCompletionClient(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
        )
    return OpenAIChatCompletionClient(model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))


# ---------- Define the agents ----------
def build_team():
    model_client = build_model_client()

    manager = AssistantAgent(
        name="manager",
        model_client=model_client,
        handoffs=["html_locator", "tester"],
        system_message=textwrap.dedent("""
            You are the Manager. Orchestrate the workflow:
            1) Receive a scenario and a URL from the user.
            2) HAND OFF both to 'html_locator'.
            3) 'html_locator' will extract and clean the HTML content of the page.
            4) Then, 'html_locator' HANDS OFF to 'researcher' with the cleaned HTML and scenario.
            5) 'researcher' will analyze the HTML and scenario, and generate structured test cases in JSON format.
            6) Then HAND OFF to 'tester' to produce Playwright-style JavaScript tests.
            7) When done, summarize the final outcome for the user and add 'TERMINATE'.
            Be brief and structured. Do not invent or add steps. Follow this flow strictly.
        """).strip()
    )

    html_locator = AssistantAgent(
        name="html_locator",
        model_client=model_client,
        handoffs=["researcher"],
        tools=[clean_html_with_playwright],
        description=textwrap.dedent("""
            An AI agent specialized in extracting and cleaning HTML content from web pages.
            Uses Playwright to retrieve and sanitize HTML for further analysis.
        """).strip(),
        system_message=textwrap.dedent("""
            You are the HTML Locator.
            Your job is to extract and clean the HTML content from a given URL using the tool clean_html_with_playwright(url).
            Once the HTML is retrieved, HAND OFF to 'researcher' along with the original scenario.
            Do not analyze or interpret the HTML. Just retrieve and pass it on.
        """).strip()
    )

    researcher = AssistantAgent(
        name="researcher",
        model_client=model_client,
        handoffs=["tester"],
        description=textwrap.dedent("""
            A helpful and general-purpose AI assistant with strong skills in HTML, CSS, JavaScript, Python, Playwright, and test case design.
        """).strip(),
        system_message=textwrap.dedent("""
            You are the Researcher.
            Your job is to generate clear and structured test cases for a given website and scenario.
            You will receive cleaned HTML and a scenario.
            Indentify the elements and its characteristics (html tag, ids, class)
            Sometimes scenarios can be ambigous so search in the code about the specific elements like text content of the elements or about the utility of that element which is involved in testing.
            Analyze both and produce test cases in JSON format. Each test case must include:
            - Test Name
            - Preconditions
            - Steps (numbered)
            - Identifiers (id/class/html-tags with text content)
            - Expected Result
            Output only valid JSON (array of objects). No extra text.
            When done, HAND OFF to 'tester'.
        """).strip()
    )

    tester = AssistantAgent(
        name="tester",
        model_client=model_client,
        handoffs=["manager"],
        description=textwrap.dedent("""
            A skilled AI assistant in writing Playwright tests using JavaScript.
        """).strip(),
        system_message=textwrap.dedent("""
            You are the Test Writer.
            You will receive structured test cases in JSON format and the HTML structure.
            Convert each test case into a Playwright test script using @playwright/test syntax and include accept cookies in test after page.goto().
            Add timeout(500) after each click.
            Follow these rules:
            - Use only the provided test cases.
            - Do not invent or assume functionality.
            - Each test must be self-contained and runnable.
            - Include comments for clarity.
            - Map JSON fields to Playwright code as follows:
            * testName → test("...")
            * preconditions → setup code or comments
            * steps → Playwright commands or comments
            * identifiers → used to locate elements
            * expectedResult → assertions
            Output only JavaScript code, ready to be placed in a single file.
            Output will be the Javascript code ready to be put in one file, so do not add duplicated imports, variables or constants. 
            Generate a Javascript Playwright code clean, to be ready for testing. Without duplicated code/imports or variable/constants.
            Wrap code in a code block text (/```javascript ), which can be extracted with regex formula /```javascript([\s\S]*?)```/g.exec(inputText) where input text is the whole final text 
            When done, HAND OFF to 'manager'.
        """).strip()
    )

    termination = TextMentionTermination("TERMINATE")
    return Swarm([manager, html_locator, researcher, tester], termination_condition=termination), model_client

async def run_pipeline(task: str) -> str:
    team, model_client = build_team()
    output_parts = []
    async for event in team.run_stream(task=task):
        content = getattr(event, "content", None)
        if isinstance(content, str) and content.strip():
            output_parts.append(content)
    await model_client.close()
    return "\n".join(output_parts) if output_parts else "(no content)"
