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
    return OpenAIChatCompletionClient(model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))


# ---------- Define the agents ----------
def build_team():
    model_client = build_model_client()

    manager = AssistantAgent(
        name="manager",
        model_client=model_client,
        handoffs=["researcher", "tester"],  # who manager can hand off to
        system_message=textwrap.dedent("""
            You are the Manager. Orchestrate the workflow:
            1) You will receive a scenario and an url and HAND OFF those to 'researcher' 
	        2) The ‘researcher’ will use tools to access the page and analyze the html content of page
            3) After ‘researcher’ analyze the content page will create some testing scenarios based on what scenario received from the ‘manager’
            4) Then HAND OFF to ’tester’ to produce one Playwright-style test(JS) to cover all scenarios received from ‘researcher’	
            5) When done, summarize the final outcome for the user and add 'TERMINATE'.
            Be brief and structured. Do not invent or add some steps, stay strict to these steps
        """).strip()
    )

    researcher = AssistantAgent(
        name="researcher",
        model_client=model_client,
        handoffs=["tester", "manager"],
        tools=[clean_html_with_playwright],
        description=textwrap.dedent("""
            A helpful and general-purpose AI assistant that has strong language skills, 
            HTML, CSS, Javascript, Python, Playwright and Linux command line skills
         """).strip(),
        system_message=textwrap.dedent("""
             You are the Researcher.
            Your job is to generate clear and structured test cases for a given website/url.
	        If given a URL, call clean_html_with_playwright(url).
            Analyse the html received after running the clean_html_with_playwright tool and the test scenario which will be provided to you.
	        Each test case must contain the following sections:
            Test Name – a short, descriptive title.
            Preconditions – any setup, environment, or assumptions required before execution.
            Steps – a numbered list of precise, actionable steps.
            Identifiers - id/class/html-tags with text content of the components which are involved in test 
            (id,class - are definited in html inside a tag like in this example: <div class="class-name" id="id-name">content</div>)
            (tags: <button>,<a>, <html>, <div>, <p>, <span>)                                                                                     
            Expected Result
	        All test cases must be returned in valid JSON format, as an array of objects.
            Do not include explanations, notes, or text outside of the JSON output.
            After you present findings togheter with the html of that url, HAND OFF to 'tester'.
        """).strip()
    )

    tester = AssistantAgent(
        name="tester",
        model_client=model_client,
        handoffs=["manager"],
        description=textwrap.dedent("""
            A helpful and general-purpose AI assistant that has strong language skills, 
            HTML, CSS, Javascript, Python, Playwright and Linux command line skills
        """).strip(),
        system_message=textwrap.dedent("""
            You are the Test Writer. 
            Using the “researcher” agent, get the html and test cases in JSON format.
            Your job is to convert structured test cases (provided in JSON format) into Playwright test scripts written in JavaScript, based on the html structure you received.
            Each generated test must follow these rules:
            * Input will always be a JSON array of test case objects.
            * Generate Playwright test code only for the test cases given in the JSON.
            * Do not create, assume, or invent test cases or functionality that are not explicitly present in the input JSON.
            * Each script must be self-contained and runnable without external dependencies.
            * Use Playwright’s @playwright/test syntax.
            * Include clear comments explaining key steps for readability.
            * Ensure the script reflects the exact steps and expected results from the JSON.
            * If the JSON does not provide enough detail, clearly state that more information is required instead of making assumptions.
            Mapping Rules (JSON → Playwright):
            * testName → Used as the test title inside test("...").
            * preconditions → Converted into setup code or comments before the steps.
            * steps → Each step becomes a Playwright command or descriptive comment.
            * identifiers -> each component which are involved in testing                           
            * expectedResult → Represented as an assertion (expect) at the end of the test.
            Output Requirements:
            * Provide only the JavaScript code (no extra explanations or text outside of the code block).
            * Each test case must be returned as a separate test function.
            * Provide the Javascript code ready to be put in one file, so do not add duplicated imports, variables or constants.                           
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
