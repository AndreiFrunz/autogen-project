import os, json, asyncio, subprocess, textwrap, re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv

# --- AutoGen Core imports (Core API) ---
from autogen_core import  SingleThreadedAgentRuntime, TopicId, MessageContext, RoutedAgent, message_handler, type_subscription

from autogen_core.models import  ChatCompletionClient, SystemMessage, UserMessage, AssistantMessage, LLMMessage

from autogen_ext.models.openai import OpenAIChatCompletionClient

# --- Playwright (async) ---
from playwright.async_api import async_playwright

# --- Prompts ---
from tools.prompts import MANAGER_BRIEF, EXPANDER_PROMPT, SELECTOR_MINER_PROMPT, TEST_WRITER_PROMPT

load_dotenv()

# -------------------- Message types --------------------
@dataclass
class ScrapeRequest:
    url: str
    scenario: str
    headers: Optional[Dict[str, str]] = None

@dataclass
class ExpandInput:
    scenario: str
    dom_digest: List[Dict[str, Any]]
    base_url: str

@dataclass
class ExpandOutput:
    cases: List[Dict[str, Any]]
    dom_digest: List[Dict[str, Any]]
    base_url: str

@dataclass
class MineRequest:
    dom_digest: List[Dict[str, Any]]
    cases: List[Dict[str, Any]]

@dataclass
class SelectorMap:
    selectors: Dict[str, Dict[str, str]]
    cases: List[Dict[str, Any]]

@dataclass
class WriteRequest:
    base_url: str
    test_cases: List[Dict[str, Any]]
    selectors: Dict[str, Dict[str, str]]

@dataclass
class FileMap:
    files: Dict[str, str]
    base_url: str

@dataclass
class ReviewRequest:
    files: Dict[str, str]
    dom_digest: List[Dict[str, Any]]

@dataclass
class ReviewDecision:
    approved: bool
    files: Dict[str, str]
    notes: str
    base_url: str

@dataclass
class RunRequest:
    files: Dict[str, str]
    base_url: str

@dataclass
class RunResult:
    passed: int
    failed: int
    total: int
    exit_code: int
    stderr: str

# -------------------- Small helpers --------------------
def first_json_block(text: str) -> Any:
    """Extract first JSON object/array from a string."""
    m = re.search(r'(\{.*\}|\[.*\])', text, re.S)
    if not m: raise ValueError("No JSON found.")
    return json.loads(m.group(1))

def base_of(url: str) -> str:
    # e.g. https://a.b/c/d -> https://a.b
    parts = url.split("/")
    return "/".join(parts[:3]) if len(parts) >= 3 else url

# -------------------- Agents --------------------
@type_subscription(topic_type="Scrape")
class Scraper(RoutedAgent):
    def __init__(self) -> None:
        super().__init__("Scraper / DOM Collector")

    @message_handler
    async def handle(self, msg: ScrapeRequest, ctx: MessageContext) -> None:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128 Safari/537.36"),
                locale="en-US",
                extra_http_headers=msg.headers or {"Accept-Language": "en-US,en;q=0.9"},
                viewport={"width": 1366, "height": 900},
            )
            page = await context.new_page()
            await page.goto(msg.url, wait_until="domcontentloaded", timeout=30000)

            # Compact DOM digest of interactive-ish elements
            dom_digest = await page.evaluate("""                    () => {
              const pickAttrs = (el) => {
                const o={}; for (const a of el.attributes)
                  if (a.name.startsWith('data-')||['id','name','placeholder'].includes(a.name)) o[a.name]=a.value;
                return o;
              };
              const textish = (el) => (el.innerText||el.textContent||"").trim().replace(/\s+/g," ").slice(0,120);
              const role = (el) => el.getAttribute('role');
              const name = (el) => el.ariaLabel || el.getAttribute('aria-label') || el.name || el.title || "";
              const nodes = document.querySelectorAll('a,button,input,select,textarea,[role],[type=submit],[type=button]');
              const items=[];
              for(const el of Array.from(nodes).slice(0,800)){
                const cls=(el.className||'').toString().trim().split(/\s+/).filter(Boolean).slice(0,8);
                items.push({
                  tag: el.tagName.toLowerCase(),
                  role: role(el)||undefined,
                  name: name(el)||undefined,
                  id: el.id||undefined,
                  classes: cls,
                  attrs: pickAttrs(el),
                  label: el.labels && el.labels[0] ? el.labels[0].innerText.trim() : undefined,
                  placeholder: el.getAttribute('placeholder')||undefined,
                  text: textish(el),
                  visible: !!(el.offsetWidth||el.offsetHeight||el.getClientRects().length)
                });
              }
              return items;
            }
            """)

            await browser.close()

        await self.publish_message(
            ExpandInput(scenario=msg.scenario, dom_digest=dom_digest, base_url=base_of(msg.url)),
            topic_id=TopicId(type="Expand", source=self.id.key),
        )

class LLMBacked(RoutedAgent):
    """Base for LLM-powered agents."""
    def __init__(self, description: str, sys_prompt: str, model_client: ChatCompletionClient) -> None:
        super().__init__(description)
        self._sys = sys_prompt
        self._model = model_client

    async def _complete_json(self, user_obj: Dict[str, Any]) -> Any:
        history: List[LLMMessage] = [SystemMessage(content=self._sys)]
        history.append(UserMessage(content=json.dumps(user_obj), source="user"))
        result = await self._model.create(history)
        return first_json_block(result.content)

@type_subscription(topic_type="Expand")
class Expander(LLMBacked):
    @message_handler
    async def handle(self, msg: ExpandInput, ctx: MessageContext) -> None:
        cases = await self._complete_json({"scenario": msg.scenario, "dom_digest": msg.dom_digest})
        await self.publish_message(
            ExpandOutput(cases=cases, dom_digest=msg.dom_digest, base_url=msg.base_url),
            topic_id=TopicId(type="MineSelectors", source=self.id.key),
        )

@type_subscription(topic_type="MineSelectors")
class Miner(LLMBacked):
    @message_handler
    async def handle(self, msg: ExpandOutput, ctx: MessageContext) -> None:
        # gather logical keys used in steps
        keys = sorted({
            step["target"] for c in msg.cases for step in c.get("steps", [])
            if isinstance(step.get("target"), str) and not step["target"].startswith("/")
        })
        selectors = await self._complete_json({"dom_digest": msg.dom_digest, "required_keys": keys})
        await self.publish_message(
            SelectorMap(selectors=selectors, cases=msg.cases),
            topic_id=TopicId(type="WriteTests", source=self.id.key),
        )

@type_subscription(topic_type="WriteTests")
class Writer(LLMBacked):
    @message_handler
    async def handle(self, msg: SelectorMap, ctx: MessageContext) -> None:
        files = await self._complete_json({
            "base_url": ctx.session.get("base_url", ""),
            "test_cases": msg.cases,
            "selectors": msg.selectors
        })
        # Expect {"files": {...}}
        files = files.get("files", files)
        await self.publish_message(
            FileMap(files=files, base_url=ctx.session.get("base_url", "")),
            topic_id=TopicId(type="User", source=self.id.key),
        )

@type_subscription(topic_type="Reflect")
class Reviewer(RoutedAgent):
    """Lightweight reflection: verify expected files exist; otherwise pass-through."""
    def __init__(self) -> None:
        super().__init__("Reviewer")

    @message_handler
    async def handle(self, msg: FileMap, ctx: MessageContext) -> None:
        notes, ok = [], True
        required = ["src/generated/selectors.ts", "src/generated/specs/generated.spec.ts"]
        for path in required:
            if path not in msg.files:
                ok = False; notes.append(f"Missing {path}")
        await self.publish_message(
            ReviewDecision(approved=ok, files=msg.files, notes="; ".join(notes), base_url=msg.base_url),
            topic_id=TopicId(type="Run", source=self.id.key),
        )

@type_subscription(topic_type="Run")
class Runner(RoutedAgent):
    def __init__(self) -> None:
        super().__init__("Runner & Reporter")

    @message_handler
    async def handle(self, msg: ReviewDecision, ctx: MessageContext) -> None:
        # write files
        for path, content in msg.files.items():
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f: f.write(content)

        # ensure config file exists
        if not os.path.exists("playwright.config.ts"):
            with open("playwright.config.ts", "w", encoding="utf-8") as f:
                f.write(textwrap.dedent("""                        import { defineConfig, devices } from '@playwright/test';
                export default defineConfig({
                  testDir: './src/generated/specs',
                  reporter: [['list'], ['html']],
                  use: { baseURL: process.env.BASE_URL || 'http://localhost:3000', headless: true },
                  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
                });
                """))

        # run tests
        env = {**os.environ, "BASE_URL": msg.base_url}
        proc = subprocess.run(
            ["npx", "playwright", "test", "src/generated/specs", "--reporter=json"],
            text=True, capture_output=True, env=env
        )
        stdout = proc.stdout.strip() or "{}"
        try:
            report = json.loads(stdout)
        except Exception:
            report = {"raw": stdout}

        # summarize
        total = passed = failed = 0
        def walk(suites):
            nonlocal total, passed, failed
            for s in suites or []:
                walk(s.get("suites"))
                for t in s.get("tests", []):
                    total += 1
                    if all(r.get("status") == "passed" for r in t.get("results", [])): passed += 1
                    else: failed += 1
        walk(report.get("suites", []))
        print(f"\n=== Playwright Summary ===\nPassed: {passed}  Failed: {failed}  Total: {total}\nExit: {proc.returncode}")
        if proc.stderr: print("\n[stderr]\n", proc.stderr)

        await self.publish_message(
            RunResult(passed=passed, failed=failed, total=total, exit_code=proc.returncode, stderr=proc.stderr),
            topic_id=TopicId(type="Done", source=self.id.key),
        )

# -------------------- Wiring & boot --------------------
async def main(url: str, scenario: str) -> None:
    runtime = SingleThreadedAgentRuntime()

    # Model client (OpenAI); requires OPENAI_API_KEY
    model_name = os.environ.get("MODEL_NAME", "gpt-4o-mini")
    model_client: ChatCompletionClient = OpenAIChatCompletionClient(model=model_name)

    # Register agents
    await Scraper.register(runtime, "Scrape", lambda: Scraper())
    await Expander.register(runtime, "Expand", lambda: Expander("Expander", EXPANDER_PROMPT, model_client))
    await Miner.register(runtime, "MineSelectors", lambda: Miner("Selector Miner", SELECTOR_MINER_PROMPT, model_client))
    await Writer.register(runtime, "WriteTests", lambda: Writer("Test Writer", TEST_WRITER_PROMPT, model_client))
    # await Reviewer.register(runtime, "Reflect", lambda: Reviewer())
    # await Runner.register(runtime, "Run", lambda: Runner())

    # Start runtime and set shared session values
    runtime.start()
    runtime._context.session["base_url"] = base_of(url)  # convenience for Writer/Runner

    # Kick off
    await runtime.publish_message(ScrapeRequest(url=url, scenario=scenario), TopicId(type="Scrape", source="default"))

    # Stop when idle
    await runtime.stop_when_idle()

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--scenario", required=True)
    args = ap.parse_args()
    asyncio.run(main(args.url, args.scenario))
