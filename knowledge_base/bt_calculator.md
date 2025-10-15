# KB: Banca Transilvania — Calculatorul de Rate (UI Knowledge Base)

This knowledge base defines how UI elements on the BT “Calculatorul de Rate” page are structured, identified, and should be interacted with when writing automated Playwright tests.

---

## 1. Page Overview

**URL:** https://www.bancatransilvania.ro/credite/calculatorul-de-rate  
**Purpose:** Simulates monthly loan repayments depending on loan type, amount, and duration.  
The page dynamically updates content without reloading. Tabs switch calculator sections, sliders and inputs update calculations, and a result panel appears after pressing **“Calculează rata”**.

---

## 2. General UI Behavior

- Uses **tabbed navigation** for different credit types (e.g., "Nevoi personale", "Imobiliar", etc.).
- The active tab is **highlighted** by:
  - Class like `.active`, `.is-active`, or `[aria-selected="true"]`.
  - Usually a border, underline, or background color change in CSS.
- Switching tabs replaces or updates a section of the DOM (without a full page reload).
- The **result panel** appears or updates dynamically after calculation.
- There is often a **cookie consent banner** that must be closed before interacting.

---

## 3. Element Definitions and Selector Guidelines

### 🟡 Tabs (Credit Type Switch)
- Usually buttons or `<a>` elements inside a container.
- Active tab: has `.active`, `.is-active`, or `aria-selected="true"`.
- Inactive tabs: visually dimmed, no “active” class.
- Clicking a tab replaces visible form content in a section element.
- **Selectors:**
  ```css
  .tab, .tabs button, .tabs a, [aria-selected="true"]

🔵 Input Fields / Sliders

Represent loan amount (“Sumă”), duration (“Durată”), or other adjustable parameters.

Implemented as numeric inputs or HTML5 range sliders.

May have corresponding labels or aria attributes.

Selectors:

input[type="number"], input[type="range"], input[name*="amount"], input[name*="sum"], input[name*="duration"]


Use text label matching (via sibling label or aria-label) to associate field purpose.

🟢 Buttons

Common button labels:

“Calculează rata” — triggers calculation.

“Vezi detalii” or “Aplică online” — opens next steps.

“Acceptă cookies” — closes cookie banner.

Selectors:

button, a.button, .btn, .btn-primary, .cta


Best practice:
Locate by partial text (e.g., page.locator('button:has-text("Calculează")')).

🔴 Result Section

Appears or updates after clicking “Calculează rata”.

Contains calculated monthly rate, interest, and other summary details.

Typically in a div with .result, .calculation, .rata-lunara, or .monthly-payment.

Use page.waitForSelector('.result', { state: 'visible' }) before assertions.

Selectors:

.result, .calculation, .monthly-payment, .rata-lunara

⚪ Cookie Consent Banner

Usually a fixed or modal div overlay with a button such as “Acceptă cookies”.

Must be dismissed before any other interaction.

Selectors:

div.cookie, div.cookies, button:has-text("Accept"), button:has-text("Acceptă"), [aria-label*="cookie"]

🟣 Common Playwright Interaction Patterns
// Accept cookies if present
if (await page.locator('button:has-text("Acceptă")').isVisible()) {
  await page.click('button:has-text("Acceptă")');
}

// Click a credit type tab
await page.locator('.tabs button:has-text("Nevoi personale")').click();
await page.waitForSelector('.tabs button.active'); // active state visible

// Fill inputs
await page.locator('input[name*="sum"], input[type="number"]').fill('50000');
await page.locator('input[name*="duration"]').fill('60');

// Trigger calculation
await page.locator('button:has-text("Calculează")').click();

// Wait for results
await page.waitForSelector('.result', { state: 'visible' });
const resultText = await page.locator('.result').innerText();

4. Key Testing Considerations

Always ensure you’re interacting only with visible elements.

After switching tabs or toggles, wait for the DOM to stabilize.

Don’t assume static positions; re-query after any tab change.

The same button labels may appear in multiple sections — always scope queries to visible containers.

Cookie banners may block clicks; close them first.

Use CSS selectors + text matching, not Playwright getByRole().

5. Assertions & Validation

Verify result text includes numeric value and currency (e.g. “LEI” or “EUR”).

Ensure amount/duration inputs update correctly after fill.

Confirm “Calculează rata” is enabled before click.

After clicking, verify .result or .calculation content changes.

6. Accessibility / Visual Cues

Active tab: strong visual highlight (color change, underline).

Disabled buttons: often grayed out with disabled attribute.

Error messages may appear inline with .error or .field-error.

End of KB.

