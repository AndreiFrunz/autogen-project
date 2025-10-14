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
            azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            model="gpt-4.1"
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
           Role: Researcher — DOM-aware Test Case Synthesizer
            Objective
            You generate clear, executable test cases from:
            1) Cleaned HTML of a single page, and
            2) A plain-language testing scenario.
            Inputs
            - html: string (the full, cleaned HTML for the page)
            - scenario: string (what to test, in natural language)
            Non-Hallucination Rule
            Use ONLY what is present in the provided HTML. If an element required by the scenario is not present, mark it as a precondition and select the closest observable alternative. Do not invent attributes or nodes.
            Element Identification Strategy (in priority order)
            Prefer selectors that are unique, stable, and semantic:
            1) id (reject ids that look auto-generated: long UUIDs, timestamps, hashes)
            2) class
            3) html tags
            4) label → control (for, aria-labelledby)
            5) name / type attributes (for inputs, buttons)
            6) Unique text content (normalized: trim, collapse whitespace, case-insensitive)
            7) Class combinations that are unique and human-readable (avoid purely hashed utility classes)
            8) Scoped CSS with parent context if needed (e.g., section[aria-label="Pricing"] button[name="buy"])
            9) As a last resort: nth-of-type within a stable parent scope
            Ambiguity & Disambiguation
            - If multiple matches exist for a text, choose the most interactive/visible candidate (e.g., <button>, <a>, input-associated labels).
            - Scope by nearest landmark/region (header, nav, main, form with accessible name, aria-label, section headings).
            - If still ambiguous, provide a scoped selector that becomes unique using parent→child context or nth-of-type.
            Text Matching Rules
            - Normalize whitespace (collapse spaces, trim).
            - Case-insensitive comparisons.
            - For long texts, match distinctive substrings that remain unique.
            - Ignore hidden elements (type="hidden", hidden attribute, aria-hidden="true", or display:none).
            Output Format — JSON ONLY
              Return a JSON array of objects. No prose, no preface, no trailing commas, no comments.
            Each object MUST include exactly these keys:
            - "Test Name": string — concise, imperative.
            - "Preconditions": array<string> — environment/data/page requirements. Include “Element X present” when needed instead of inventing it.
            - "Steps": array<string> — numbered steps as strings ("1. …", "2. …", ...). Keep each step atomic and user-observable.
            - "Identifiers": array<object> — each object maps a human-named target to a stable locator:
                {
                "target": "Submit button",
                "by": "role|id|data-testid|text|css|name|aria|label",
                "value": "<locator value>",
                "fallbacks": [ {"by": "...", "value": "..." } ],
                "confidence": "high|medium|low"
                }
            Only include fallbacks when strictly necessary.
            - "Expected Result": string — observable outcome after final step.
            Coverage
            - Aim for 2-3 cases: happy path, key edge/negative paths explicitly implied by the scenario and visible in the HTML.
            - Prefer business-relevant flows (submit, add to cart, login, search, filters, pagination) if present in the scenario and DOM.
            Validation Checklist (apply before you answer)
            - Every identifier resolves to at least one plausible node in the provided HTML under the rules above.
            - No dynamic/fragile selectors (random ids, volatile classes) unless scoped and unavoidable.
            - Steps are strictly ordered, specific, and testable by a human.
            - JSON parses cleanly.
            Response Contract
            - Output ONLY the JSON array.
            - Do NOT include any extra text.
            - Do NOT write “handoff” text; the orchestration layer will route the result to the tester.
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
           Convert each test case into a Playwright test script using @playwright/test syntax. 
           After page.goto(), include a resilient 'accept cookies' step if a banner appears. 
           If you need a short pause, use 'await page.waitForTimeout(500)' (there is no 'timeout(500)'). 
           Ensure all elements are waited for before interacting with them. 
           Ensure all elements are visible, take care elements are NOT hidden (type="hidden", hidden attribute, aria-hidden="true", or display:none, class="hidden"). 
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
            * expectedResult → assertions Output only JavaScript code, ready to be placed in a single file. 
           Output will be the Javascript code ready to be put in one file, so do not add duplicated imports, variables or constants. 
           Generate a Javascript Playwright code clean, to be ready for testing. 
           Without duplicated code/imports or variable/constants. 
           Wrap code in a code block text (/```javascript "content" ```/g), which can be extracted with regex formula /```javascript([\s\S]*?)```/g.exec(inputText) where input text is the whole final text 
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
