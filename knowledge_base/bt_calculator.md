# BT Loan Calculator – Playwright KB (Class/Attribute/XPath selectors only)

**Primary URL:** `https://www.bancatransilvania.ro/credite/calculatorul-de-rate`  
**Mirror (EN):** `https://en.bancatransilvania.ro/credits/calculatorul-de-rate` (for label parity only)

**Ground truths for assertions**

- Two products (tabs): **Nevoi Personale** & **Imobiliar-Ipotecar**; switching updates labels/controls.
- **Personal (Nevoi Personale)**: amount range **5.000–250.000 LEI**; tenor **1–5 ani**; interest **Fixă / Variabilă**.
- **Mortgage (Imobiliar-Ipotecar)**: label **„Cât costă locuința?”**, price range **7.000–1.200.000 LEI**, avans **15–50%**, presets **1/10/20/30** + **Alt interval**, interest **Fixă în primii 2 ani… / Variabilă**.
- Primary output tile: **„RATA LUNARĂ {amount} {currency}”**.

> This site renders parts of the simulator dynamically; class names can be **semantic** or **hashed**. The selector strategy below prefers class/attribute hooks and provides “fallback packs” (text, XPath) while still avoiding role-based APIs.

---

## Selector strategy (class/attr first, then text/XPath)

> Use the **first matching pack** that works in CI. Keep packs in code so the agent can fall back automatically.

### A) Root containers (choose one)

- `css=[class*="calculator"], css=[class*="simulator"], css=section[class*="credit"]`
- Fallback text anchor: `text=/Simulator de credit|Loan Simulator/i` (used only to scope a nearby container; avoid it for clicks)

### B) Product tabs (no getByRole)

- **Personal tab**:
  - Primary: `css=.tabs .tab--personal, css=[class*="tabs"] [class*="personal"]`
  - Fallback (text engine): `text=/Nevoi\\s+Personale/i`
  - XPath: `xpath=//button[contains(., "Nevoi") and contains(., "Personale")]`
- **Mortgage tab**:
  - Primary: `css=.tabs .tab--mortgage, css=[class*="tabs"] [class*="imobiliar"], css=[class*="tabs"] [class*="ipotec"]`
  - Fallback (text): `text=/Imobiliar|Ipotecar/i`
  - XPath: `xpath=//button[normalize-space()="Imobiliar-Ipotecar" or contains(., "Ipotecar")]`

### C) Core inputs

- **Personal amount** (textbox):
  - Primary: `css=input[name*="amount"], input[name*="suma"], input[class*="amount"], input[class*="suma"]`
  - Secondary: `css=[placeholder*="lei"], [inputmode="numeric"]`
  - XPath: `xpath=//label[contains(., "împrumuți")]/following::input[1]`
- **Mortgage price** (textbox):
  - Primary: `css=input[name*="pret"], input[name*="price"], input[class*="price"], input[class*="pret"]`
  - XPath: `xpath=//label[contains(translate(., "ÂĂÎȘȚáâăîșț", "AAISTaaist"), "cat costa locuinta")]/following::input[1]`
- **Sliders** (for amount/price/avans):
  - Generic: `css=[class*="slider"] input[type="range"], input[type="range"]`
- **Currency toggle**:
  - LEI: `css=[class*="currency"] [class*="lei"], css=button[data-currency="LEI"], css=[data-currency="RON"]`
  - EURO: `css=[class*="currency"] [class*="eur"], css=button[data-currency="EUR"]`
- **Tenor buttons**:
  - Personal 1–5y: `css=[class*="tenor"] button` (filter by text `^([1-5])$`)
  - Mortgage presets: `css=[class*="tenor"] button` (filter by text `^(1|10|20|30)$`) + **Alt interval**: `text=/Alt interval/i` then `css=input[name*="ani"], input[class*="ani"]`
- **Interest type**:
  - Personal: `css=[class*="interest"] [class*="fix"], [data-interest*="fixed"]`; `css=[class*="interest"] [class*="variabil"], [data-interest*="variable"]`
  - Mortgage intro-fix: `text=/Fix(ă|a)\\s+în primii\\s+2\\s+ani/i`; generic attr: `css=[data-interest*="intro"]`
- **Salary at BT / Insurance / Schedule** (binary/radio):
  - `css=[class*="salary"] [class*="da"], [class*="salary"] [class*="nu"]`
  - `css=[class*="asigur"], [data-toggle*="insurance"] [data-value]`
  - `css=[class*="schedule"] [class*="egale"], [class*="schedule"] [class*="descresc"]`

### D) Results, actions, messages

- **Monthly rate tile**:
  - Container: `css=[class*="rata"], [class*="result"], [class*="monthly"]`
  - Amount node under tile: `css=[class*="rata"] [class*="amount"], [class*="result"] [class*="value"]`
  - Fallback text: `text=/^Rata\\s+lunara|Rata\\s+lunară/i` (for scoping only)
- **Settings entry / apply**:
  - Open: `css=button[class*="schimba"], a[class*="schimba"], [data-action="open-settings"]`
  - Apply: `css=button[class*="vezi"], [data-action="apply-settings"]`
- **Validation hints (min/max)**:
  - `css=[class*="helper"], [class*="error"], [class*="hint"]`
  - Text patterns:
    - Min: `/Suma\\s+minim[ăa]\\s+pe care o poți împrumuta este/i`
    - Max: `/Suma\\s+maxim[ăa]\\s+pe care o poți împrumuta este/i`
- **Error placeholder** (on failure):
  - `css=[class*="error"], [data-state="error"]`
  - Text: `/Calcul indisponibil momentan/i`

---

## Ranges & rules (assertions)

- **Personal amount:** **min 5.000 LEI**, **max 250.000 LEI**; tenor **1–5 ani**; interest **Fixă/Variabilă**.
- **Mortgage price:** **min 7.000 LEI**, **max 1.200.000 LEI**; **Avans 15–50%** (min/max lei hints update with price); tenor presets **1/10/20/30** + **Alt interval** (custom years).
- **Currency:** **LEI / EURO** toggle updates symbol & recomputes.
- **Primary output:** **„RATA LUNARĂ”** shows recalculated amount after a valid change.

---

## Timing budgets (for perf checks)

- Recalc after **direct control** (typing/slider): **≤ 500 ms** to update rate tile.
- Recalc after **settings apply**: **≤ 1,000 ms** after clicking **„Vezi noul calcul”**.
- On failure: show **error placeholder** and **hide previous rate** (no stale values).

_(Budgets are QA requirements; not guaranteed by site copy.)_

---

## Input & formatting rules (UI expectations)

- Numeric fields accept **digits only** while typing; apply **thousands separators** on blur (`250.000`).
- **Slider ↔ textbox** stay synchronized.
- **Tab switch** should **retain per-product state** (returning to a tab restores its last values).

---

---

## Cookie Banner Handling (avoid strict mode violations)

The site may render **two overlapping cookie containers** at once (e.g., `.gdprcookie-wrapper` and `.gdprcookie`). Using `page.locator()` on a **comma selector** can trigger **Playwright strict mode** errors when multiple nodes match. **Do not** rely on `locator(...).isVisible()` for union selectors.

### Strategy

- Use **element handles** (`page.$`, `page.$$`) to pick **the first visible** banner container.
- Prefer **scoped search** into the picked container to find the **accept button**.
- Provide multiple **button selector fallbacks**: `.btn-ac`, `[data-accept="cookies"]`, `button:has-text("Accept")`, `button:has-text("De acord")`, etc.
- If nothing is visible within a short window, **return silently**.

### Robust helper (no `getByRole`, limited use of `locator`)

```ts
export async function acceptCookiesIfPresent(
  page: import("@playwright/test").Page,
  timeoutMs = 2500
) {
  const t0 = Date.now();
  const containerSelectors = [
    ".gdprcookie-wrapper",
    ".gdprcookie",
    '[class*="cookie"]',
  ];
  const acceptSelectors = [
    ".btn-ac",
    '[data-accept="cookies"]',
    'button:has-text("Accept")',
    'button:has-text("ACCEPT")',
    'button:has-text("De acord")',
    'button:has-text("Sunt de acord")',
  ];

  // poll for a visible container until timeout
  let container = null;
  while (!container && Date.now() - t0 < timeoutMs) {
    for (const sel of containerSelectors) {
      const candidates = await page.$$(sel);
      for (const c of candidates) {
        if (await c.isVisible()) {
          container = c;
          break;
        }
      }
      if (container) break;
    }
    if (!container) await page.waitForTimeout(100);
  }
  if (!container) return; // nothing to do

  // find and click the first visible accept button inside container
  for (const btnSel in acceptSelectors) {
    /* placeholder to keep TS happy */
  }
  for (const btnSel of acceptSelectors) {
    const btn = await container.$(btnSel);
    if (btn && (await btn.isVisible())) {
      await btn.click();
      await page.waitForTimeout(200);
      return;
    }
  }

  // fallback: try clicking any visible button inside the container
  const anyButtons = await container.$$("button");
  for (const b of anyButtons) {
    const txt = (await b.textContent())?.trim().toLowerCase() || "";
    if (
      (await b.isVisible()) &&
      /accept|de acord|sunt de acord|ok|înțeleg|inteleg/.test(txt)
    ) {
      await b.click();
      await page.waitForTimeout(200);
      return;
    }
  }
}
```

### Why this avoids strict-mode errors

- `page.$` / `page.$$` **do not enforce strictness**; they simply return the first or all matches.
- We **scope** the button search **within the chosen container**, guaranteeing a single interaction target.
- We support **multiple UI variants** (RO/EN copy, data attributes, class names).

## Canonical test blueprints (no role/locator APIs)

> All steps use `page.click('css=...')`, `page.fill('css=...')`, `page.waitForSelector('css=...')`, **ElementHandle**s, and **XPath/text engines**—never `getByRole`, never `page.locator(...)`.

### 1) Tabs render & switch + state retention

- **Steps**
  1. `await page.waitForSelector('css=[class*="tabs"]');`
  2. Click mortgage tab: `await page.click('text=/Imobiliar|Ipotecar/i');`
  3. Assert mortgage core label nearby: `await page.waitForSelector('text=/C(â|a)t cost[ăa] locuin[tț]a\\?/i');`
  4. Fill a price: `await page.fill('css=input[name*="pret"], input[name*="price"]', '120000');`
  5. Click personal tab: `await page.click('text=/Nevoi\\s+Personale/i');`
  6. Fill personal amount: `await page.fill('css=input[name*="amount"], input[name*="suma"]', '50000');`
  7. Switch back to mortgage: `await page.click('text=/Imobiliar|Ipotecar/i');`
- **Assertions**
  - Price field retains previous number (read via element handle `.inputValue()`).
  - Rate tile changes after each tab switch: compare previous vs new text from `await (await page.waitForSelector('css=[class*="rata"]')).textContent()` within 1s.

### 2) Personal amount validation & slider sync

- **Steps**
  - Below min: fill `4999` → expect min helper: `await page.waitForSelector('text=/Suma minim[ăa]/i');`
  - Above max: fill `250001` → expect max helper: `await page.waitForSelector('text=/Suma maxim[ăa]/i');`
  - Boundary values `5000` and `250000` accepted.
  - Drag range slider to ends: `await page.hover('input[type="range"]'); await page.mouse.down(); ...`
- **Assertions**
  - Thousand separators after blur (read `textContent()` close to the input or formatted mirror field).
  - Rate tile updates ≤ 500 ms on valid change.

### 3) Mortgage price + avans dynamics

- **Steps**
  - Switch to mortgage tab → set price to `7000` then `1200000`.
  - Adjust avans slider to **15%** then **50%**: use drag or keyboard (see helper).
- **Assertions**
  - Hints appear: `text=/Avansul minim este/i` and `text=/Avansul maxim este/i` with lei amounts.
  - Rate tile changes after price/percent edits (≤ 500 ms).

### 4) Tenor presets & “Alt interval” flow (mortgage)

- **Steps**
  - Click `text=/^(1|10|20|30)$/` buttons (e.g., `page.click('text=/^10$/')`).
  - Click `text=/Alt interval/i` → fill `css=input[name*="ani"], input[class*="ani"]` with e.g. `17`.
  - Click **apply**: `await page.click('css=button[class*="vezi"], [data-action="apply-settings"]');`
- **Assertions**
  - After apply, summary view shows updated rate within 1s.

### 5) Interest & currency impact

- **Steps**
  - **Personal**: record rate text; click fixed/variable via class hooks:  
    `await page.click('css=[class*="interest"] [class*="variabil"]');`  
    `await page.click('css=[class*="interest"] [class*="fix"]');`
  - **Currency**: `await page.click('css=[class*="currency"] [class*="eur"], [data-currency="EUR"]');`
- **Assertions**
  - Rate text changes after each toggle; currency symbol updates to **EUR** (then back to **LEI**).

### 6) Settings deferred apply

- **Steps**
  - Open settings: `await page.click('css=button[class*="schimba"], a[class*="schimba"]');`
  - Change multiple params (interest, tenor, schedule) inside config panel.
  - Close via **Închide** (or back): `await page.click('text=/Închide|Înapoi|Close/i');`
  - Assert summary **unchanged** (compare cached rate).
  - Reopen, change again, click **apply**: `await page.click('css=button[class*="vezi"]');`
- **Assertions**
  - Only after **apply** does the rate change (≤ 1,000 ms).

### 7) Failure placeholder (mocked)

- **Steps**
  - `await page.route('**/calc*', route => route.abort());` (or return 500)
  - Trigger recalculation (change amount).
- **Assertions**
  - Placeholder `text=/Calcul indisponibil momentan/i` appears; previous rate text is **not** visible.

---

## Helper snippets (class/attr/XPath only)

```ts
// wait and read text from a CSS target (no Locator API)
async function getText(page, selector) {
  const el = await page.waitForSelector(selector, { state: "visible" });
  return (await el.textContent())?.trim() ?? "";
}

// assert rate changes without getByRole/locator
const rateSel = 'css=[class*="rata"], [class*="result"], [class*="monthly"]';
const before = await getText(page, rateSel);
// ... make a change ...
await page.waitForFunction(
  (sel, prev) => {
    const el = document.querySelector(sel);
    return el && el.textContent && el.textContent.trim() !== prev;
  },
  rateSel,
  before,
  { timeout: 1000 }
);

// set slider by keyboard (safer than pixel coords)
async function sliderStepRight(page, sliderSel, steps = 10) {
  const s = await page.waitForSelector(sliderSel);
  await s.focus();
  for (let i = 0; i < steps; i++) await page.keyboard.press("ArrowRight");
}

// money pattern for RO format
const moneyRe = /^\\s*\\d{1,3}(\\.\\d{3})*(,\\d{2})?\\s*(LEI|EUR)\\s*$/i;
```

---

## Test data & strings (for text/XPath selectors)

- Tabs: **„NEVOI PERSONALE”**, **„IMOBILIAR-IPOTECAR”**.
- Core labels: **„Cât vrei să împrumuți?”** (personal), **„Cât costă locuința?”** (mortgage).
- Ranges: **5.000–250.000 LEI** (personal), **7.000–1.200.000 LEI** (mortgage).
- Avans hints: **„Avansul minim este {X}”**, **„Avansul maxim este {Y}”**, **15%–50%**.
- Tenor presets: **1 / 10 / 20 / 30 / Alt interval**; personal **1–5**.
- Actions: **„Schimbă calculul”**, **„Vezi noul calcul”**.
- Result title: **„Rata lunară / RATA LUNARĂ”** visible near amount.

---

## Flakiness guards (still avoiding Locator APIs)

- Prefer **attribute selectors** (`[name*=]`, `[data-*]`, `[class*=]`) over exact full class names (resilient to BEM/hashing).
- When using the **text engine** (`text=/.../i`), scope with a nearby container class, e.g.  
  `css=[class*="simulator"] >> text=/Rata lunară/i` (the `>>` chain still uses direct selector strings).
- For sliders, **keyboard arrows** are steadier than pixel drags.
- Avoid `expect(locator)`—instead read text via element handle and compare strings.

---

## Disambiguating Similar Inputs (strict-mode safe)

The simulator renders multiple inputs sharing the class `.bt-simulator-de-credit-range-slider-field-input-display`
(e.g., **amount/price** and **avans**). Using that class alone causes **strict mode** violations.

**Use these field-specific attributes:**

- **Personal amount:** `input[data-field-name="suma"]` (fallback: `input[name="suma"]`)
- **Mortgage price:** `input[data-field-name="pret"]` (fallback: `input[name="pret"]`)
- **Down payment (avans):** `input[data-field-name="avans"]`

**Scoped XPath fallback by label:**

- Personal: `xpath=//label[@id="sumaSim"]/following::input[@data-field-name="suma"][1]`
- Mortgage: `xpath=//label[contains(., "Cât costă locuința")]/following::input[@data-field-name="pret"][1]`

---

## Active Tab Detection (no reliance on class "active")

Some deployments **do not** add an `active` CSS class. Use attribute-based checks:

1. Prefer `[aria-selected="true"]` or `[data-selected="true"]` on the tab element.
2. If absent, verify **content switch** by asserting the **core label** appropriate for each tab:
   - Personal: label with id `#sumaSim` contains “împrumuți”
   - Mortgage: “Cât costă locuința?” visible near price input

Helper:

```ts
async function isTabActiveHandle(
  tabHandle: import("@playwright/test").Locator
) {
  const aria = await tabHandle.getAttribute("aria-selected");
  const dataSel = await tabHandle.getAttribute("data-selected");
  if (aria === "true" || dataSel === "true") return true;
  const cls = (await tabHandle.getAttribute("class")) || "";
  if (/(--active|active|selected)/i.test(cls)) return true;
  return false;
}
```

---

## AC1.4 Clarification (Result refresh on tab switch)

The **“Vezi noul calcul”** button may only appear inside the **settings** flow. For AC1.4, **do not click it**.  
Instead, capture `.bt-simulator-de-credit-form-result-total-value` before/after switching tabs and assert the text changes within **1s**.

---
