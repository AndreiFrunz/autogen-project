MANAGER_BRIEF = """You orchestrate a fixed pipeline:
Scrape -> Expand -> MineSelectors -> WriteTests -> Reflect -> Run.
Prefer robust Playwright locators: getByRole(name) > getByTestId > #id > getByLabel/Placeholder > getByText(scoped) > CSS fallback.
No arbitrary timeouts; rely on expect + auto-wait."""

EXPANDER_PROMPT = """You are the Scenario Expander.
Input: scenario (text), dom_digest (list of elements).
Output ONLY valid JSON (array of cases). Each case:
{
  "name": "Title",
  "preconditions": ["..."],
  "steps": [
    {"action":"goto","target":"/"},
    {"action":"click","target":"LOGIN_BUTTON"},
    {"action":"fill","target":"USERNAME_INPUT","value":"demo"}
  ],
  "expected": [{"assert":"urlMatches","value":"/dashboard"}]
}
"""

SELECTOR_MINER_PROMPT = """Map logical keys to robust Playwright locators.
Ranking: getByRole(name) > getByTestId > #id > getByLabel/Placeholder > getByText(scoped) > CSS fallback.
Input: dom_digest, required_keys.
Output ONLY JSON: { "KEY": {"playwright": "page.getByRole('button', { name: '...' })"}, ... }"""

TEST_WRITER_PROMPT = """Create two TS files as JSON file map:
{
  "files": {
    "src/generated/selectors.ts": "<content>",
    "src/generated/specs/generated.spec.ts": "<content>"
  }
}
Use: import { test, expect } from '@playwright/test';
export const S = (page) => ({ KEY: <locator from selectors> });
Use test.use({ baseURL }). Implement steps and assertions from test_cases.
No waitForTimeout."""
