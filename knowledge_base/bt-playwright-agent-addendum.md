# Knowledge Base — Playwright Agent Addendum for BT Calculator

**Target URL:** https://www.bancatransilvania.ro/credite/calculatorul-de-rate

This addendum refines selector guidance to prevent strict‑mode violations and flaky tab checks on the BT calculator.

---

## A) Golden Rules (Recap)

- **Scope first, then query.** Work inside `#bt-simulator-de-credit` or the calculator region (`getByRole('region', { name: /Alege\s+creditul|Choose\s+the\s+loan/i })`).
- **Prefer roles & accessible names.** Tabs → `role="tab"` + `aria-selected`; inputs → `getByRole('spinbutton'|'textbox', { name: /Suma|Amount/i })`.
- **If multiple matches remain**, either **filter by attribute** or interact with `.first()`; assert uniqueness with `toHaveCount(1)` only when required.

```ts
const calc = page
  .locator("#bt-simulator-de-credit")
  .first()
  .or(
    page
      .getByRole("region", { name: /Alege\s+creditul|Choose\s+the\s+loan/i })
      .first()
  );
```

---

## B) Disambiguating Numeric Inputs (Fix for strict‑mode)

The calculator renders **more than one numeric input** with the same display class (`.bt-simulator-de-credit-range-slider-field-input-display`).  
To avoid strict‑mode violations, filter by **semantic attribute**:

- **Amount** (loan amount): `data-field-name="suma"`
- **Down payment / Advance**: `data-field-name="avans"`

```ts
// Amount input (unique)
const amountInput = calc
  .locator(
    'input.bt-simulator-de-credit-range-slider-field-input-display[data-field-name="suma"]'
  )
  .first();
await expect(amountInput).toBeVisible();
const amountValue = await amountInput.inputValue();

// Down payment (only visible for mortgage)
const downPaymentInput = calc
  .locator(
    'input.bt-simulator-de-credit-range-slider-field-input-display[data-field-name="avans"]'
  )
  .first();
```

> Always **avoid** querying by the generic class alone; it matches multiple inputs and triggers strict‑mode errors.

---

## C) Tab Locators & Active State (Replace class comparisons)

Do **not** compare raw class strings between tabs; both share a base class. Use **ARIA first**: `aria-selected="true"` on `role="tab"`.  
When ARIA is missing, detect the **panel content switch** and/or **modifier attributes**.

```ts
// Scoped tablist
const tablist = calc
  .getByRole("tablist")
  .first()
  .or(calc.locator(".bt-simulator-de-credit-categories-items").first());

const personalTab = tablist
  .getByRole("tab", { name: /nevoi personale/i })
  .first()
  .or(tablist.getByRole("button", { name: /nevoi personale/i }).first());
const mortgageTab = tablist
  .getByRole("tab", { name: /imobiliar|ipotecar/i })
  .first()
  .or(tablist.getByRole("button", { name: /imobiliar|ipotecar/i }).first());

await expect(personalTab).toBeVisible();
await expect(mortgageTab).toBeVisible();

// ARIA‑first
if ((await mortgageTab.getAttribute("role")) === "tab") {
  // Exactly one tab selected before
  const selBefore = [
    await personalTab.getAttribute("aria-selected"),
    await mortgageTab.getAttribute("aria-selected"),
  ].filter((v) => v === "true");
  expect(selBefore).toHaveLength(1);

  await mortgageTab.click();
  await expect(mortgageTab).toHaveAttribute("aria-selected", "true");
  await expect(personalTab).not.toHaveAttribute("aria-selected", "true");
} else {
  // Fallback: modifier on self or nearest parent
  await mortgageTab.click();
  await expect(mortgageTab).toHaveClass(/active|selected|current/i);
  await expect(personalTab).not.toHaveClass(/active|selected|current/i);
}
```

**Functional confirmation of tab switch (panel‑based):**
Instead of visual classes, assert the **mortgage‑only** field appears after selecting mortgage:

```ts
await personalTab.click();
await expect(downPaymentInput).toBeHidden(); // 'avans' not visible on personal

await mortgageTab.click();
await expect(downPaymentInput).toBeVisible(); // 'avans' visible on mortgage
```

This satisfies “active tab highlighted / inactive de‑emphasized” by verifying the **resulting UI state** when ARIA is unavailable.

---

## D) AC1.2 — Switching Tabs Updates Labels & Ranges (Robust Template)

Avoid `#sumaSim` label ids; instead, read the **accessible label** or the **fieldset legend** nearest to the input. If not available, use a scoped text probe **next to** `amountInput`.

```ts
// Read label/legend near amount input
const amountField = amountInput.locator(
  'xpath=ancestor::div[contains(@class,"range-slider")][1]'
);
const labelNode = amountField
  .getByText(/suma|amount/i)
  .first()
  .or(calc.getByLabel(/suma|amount/i).first());

const labelBefore = await labelNode.textContent();
const valueBefore = await amountInput.inputValue();

await mortgageTab.click();

// Re‑query nodes (DOM can re‑render)
const amountInput2 = calc
  .locator(
    'input.bt-simulator-de-credit-range-slider-field-input-display[data-field-name="suma"]'
  )
  .first();
const amountField2 = amountInput2.locator(
  'xpath=ancestor::div[contains(@class,"range-slider")][1]'
);
const labelNode2 = amountField2
  .getByText(/suma|amount/i)
  .first()
  .or(calc.getByLabel(/suma|amount/i).first());

const labelAfter = await labelNode2.textContent();
const valueAfter = await amountInput2.inputValue();

expect(labelAfter?.trim()).not.toBe(labelBefore?.trim());
expect(valueAfter).not.toBe(valueBefore);
```

> **Re‑query after tab switch.** The calculator may re‑render inputs; fresh locators are safer than reusing prior references.

---

## E) AC1.4 — Results Refresh on Tab Switch

Scope to the **results container** inside the calculator and extract the number close to the “Monthly rate” label. Use `toHaveText` for auto‑waiting.

```ts
const results = calc.locator(".bt-simulator-de-credit-form-result").first();
const monthlyLabel = results
  .getByText(/rata lunară|monthly (installment|rate)/i)
  .first();
const monthlyValue = monthlyLabel
  .locator("..")
  .locator("text=/[0-9][0-9 .,:-]*/")
  .first();

await personalTab.click();
const ratePersonal = await monthlyValue.textContent();

await mortgageTab.click();
await expect(monthlyValue).toHaveText(/\\d/); // ensure refreshed
const rateMortgage = await monthlyValue.textContent();

expect(rateMortgage?.trim()).not.toBe(ratePersonal?.trim());
```

---

## F) Strict‑Mode Safe Cookie Helper

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

---

## G) Checklist for the Agent

- [ ] Scope to `#bt-simulator-de-credit` or the calculator region before any queries.
- [ ] For **amount**, target `[data-field-name="suma"]`; for **down payment**, target `[data-field-name="avans"]`.
- [ ] For tabs, assert **ARIA (`aria-selected`)** when `role="tab"` exists; otherwise assert **panel content change** (e.g., `avans` presence).
- [ ] Re‑query elements **after switching tabs** to avoid stale references.
- [ ] Never compare class strings between tabs; avoid generic classes for input selection.
- [ ] When multiple matches remain, use `.first()`; assert `toHaveCount(1)` only when uniqueness is a requirement.
