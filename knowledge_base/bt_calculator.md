# Knowledge Base for BT Agents

> 🔗 Include addendum: **bt-playwright-agent-addendum.md**  
> Precedence: **Addendum overrides base** where instructions conflict.

---

## 1) Selection & Scoping Rules

- **Scope before you query.** Find the smallest stable container (region, dialog, form), then query _within_ it.  
  Prefer locators in this order: `getByRole` → `getByLabel` → `getByPlaceholder` → `getByText`.  
  Treat `data-testid` as an explicit contract and last resort.
- **User-first locators.** Favor **role + accessible name**. Example:  
  `page.getByRole('button', { name: /apply|aplică/i })`.
- **Strict mode implications.** Actions/assertions on a locator that matches >1 element throw.  
  Resolve by scoping, adding role/name, or using `.first()`. If uniqueness matters, assert `await expect(locator).toHaveCount(1)`.

---

## 2) Active State & Accessibility

- Prefer **ARIA** over styling to determine state. For tabs, use `role="tab"` + `aria-selected="true"`.
- Fall back to modifiers only if ARIA is absent: class includes `active|selected|current`, or attributes `data-state="active"`, `data-active="true"`, `aria-current="true"`.
- Always **click** by accessible element (e.g., the tab/button), not its decorative wrapper.

---

## 3) Assertions & Auto‑waiting

- Use Playwright’s built‑in `expect` — it **auto‑waits**. Avoid arbitrary `waitForTimeout`.  
  Examples: `toBeVisible`, `toHaveText`, `toHaveAttribute`, `toHaveURL`, `toHaveCount`.
- Prefer **stateful assertions** over reading values into variables and asserting with bare `expect` — this leverages retries and reduces flake.
- Keep assertions **close to interactions** so waiting windows are short and intent is clear.

---

## 4) Flake Killers

- Avoid **global text searches**; always **scope + role** to prevent matching headers/footers/hidden nodes.
- Keep tests small and focused; avoid cross‑test dependencies. Reset state per test.
- Handle **consent/cookie banners** with a **scoped** helper that uses `.first()` to avoid strict‑mode violations.
- Prefer `page.waitForLoadState('domcontentloaded')` or assertion auto‑waits over sleeps.

---

## 5) Patterns & Structure

- Adopt **Page Object Model** once suites grow. Keep:
  - **Interactions** in page objects, **assertions** in specs.
  - Page objects minimal (no test logic, no assertions except tiny sanity checks).
- Use **fixtures** for setup/teardown and shared context (auth session, permissions, device).

---

## 6) Debuggability

- Use **UI Mode** / `--debug` to step through.
- Enable **trace** and **screenshots/videos on failure** in CI. Keep traces “on failure” to save space.
- Add targeted logging via `test.info().annotations.push(...)` for dynamic values (e.g., discovered min/max).

---

## 7) Known Pitfalls (with fixes)

- **Strict mode violation** (multiple matches): scope to a container, add role+name, or use `.first()`; assert uniqueness when required.
- **Brittle CSS**: don’t drive interactions by CSS class or structure; use roles/labels. CSS is fine for _scoping only_.
- **Timing races**: use auto‑waiting assertions; avoid `waitForTimeout`.
- **Hidden/overlayed elements**: assert `toBeVisible()` or `toBeEnabled()` before clicking; consider `force: true` only as a last resort with a comment.

---

## 8) Reusable Snippets

### 8.1 Scoped tab selection with ARIA‑first checks

```ts
// Scope to smallest stable container
const region = page
  .getByRole("region", {
    name: /calculator|simulator|choose the loan|alege creditul/i,
  })
  .first();
await expect(region).toBeVisible();

// Tablist or fallback container
const tablist = region.getByRole("tablist").first().or(region);

// Tabs by role + name (fallback to buttons)
const personal = tablist
  .getByRole("tab", { name: /personal|nevoi personale/i })
  .first()
  .or(
    tablist.getByRole("button", { name: /personal|nevoi personale/i }).first()
  );
const mortgage = tablist
  .getByRole("tab", { name: /mortgage|imobiliar|ipotecar/i })
  .first()
  .or(
    tablist
      .getByRole("button", { name: /mortgage|imobiliar|ipotecar/i })
      .first()
  );

await expect(personal).toBeVisible();
await expect(mortgage).toBeVisible();

await mortgage.click();

// ARIA‑first active state
if ((await mortgage.getAttribute("role")) === "tab") {
  await expect(mortgage).toHaveAttribute("aria-selected", "true");
  await expect(personal).not.toHaveAttribute("aria-selected", "true");
} else {
  await expect(mortgage).toHaveClass(/active|selected|current/i);
  await expect(personal).not.toHaveClass(/active|selected|current/i);
}
```

### 8.2 Strict‑mode–safe cookie banner helper

```ts
export async function acceptCookies(page: Page) {
  const banners = page.locator(".gdprcookie-wrapper, .gdprcookie");
  if ((await banners.count()) === 0) return;

  const banner = banners.first();
  if (!(await banner.isVisible().catch(() => false))) return;

  const accept = banner
    .getByRole("button", {
      name: /accept|accept toate|de acord|sunt de acord/i,
    })
    .first();
  if (await accept.isVisible().catch(() => false)) {
    await accept.click();
    await page.waitForLoadState("domcontentloaded");
  }
}
```

### 8.3 Uniqueness when required

```ts
const primaryCta = region.getByRole("button", { name: /apply|aplică/i });
await expect(primaryCta).toHaveCount(1);
await primaryCta.first().click();
```

### 8.4 Numeric extraction (scoped results)

```ts
const results = region.locator('[class*="result"], [data-result]').first();
const monthly = results
  .getByText(/monthly (installment|rate)|rata lunară/i)
  .first();
const monthValue = await monthly
  .locator("..")
  .locator("text=/[0-9][0-9 .,:-]*/")
  .first()
  .textContent();
```

### 8.5 Guard for multi‑match before action

```ts
const candidates = region.getByRole("button", { name: /continue|următor/i });
await expect(candidates).toHaveCount(1);
await candidates.first().click();
```

---

## 9) Suggested Test Structure

- **Arrange**: navigate + accept cookies + scope container.
- **Act**: minimal interactions to reach the state.
- **Assert**: stateful expectations (prefer ARIA & roles).
- **Clean**: optional (e.g., close modal) to keep state tidy for parallel runs.

---

## 10) Optional Conventions for Agents

- Always provide a short **selector rationale** in comments near non‑trivial locators.
- When ranges/labels are dynamic, **discover** them at runtime (read visible hints) and log via `test.info().annotations` for traces.
- If multiple matches remain after scoping, interact with `.first()`; if uniqueness is a requirement, assert `toHaveCount(1)`.

---

## References (to share with humans; agents don’t need to click)

- Playwright: Locators & roles (official docs)
- Playwright: Writing tests & expect assertions (official docs)
- Playwright: Best practices, fixtures, and POM (official docs)
- Playwright: Trace viewer & debugging (official docs)
- Checkly & community guides on “user-first” selectors and anti‑flake patterns
