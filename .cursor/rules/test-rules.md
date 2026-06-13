# Test Automation Rules

These rules govern test step execution and final script output. They complement the test steps with workflow, per-step classification, and logging details.

Used by **test-agent** when invoked by **test-runner** (see `.cursor/commands/test-runner.md` and `.cursor/agents/test-agent.md`).

---

## Orchestration (test-runner → test-agent)

| Role | Responsibility |
|------|----------------|
| **test-runner** | Reads Excel; one row = one test name; passes `excel_path`, `row_number`, and **all** step definitions for that test name in **one** call to test-agent |
| **test-agent** | Runs **every** step in `step_definitions` sequentially in **one session**; writes **Result** and **Remark** to `excel_path` for that test name; returns **one** verdict when done |
| **test-rules** (this file) | Protocols for executing each step within that single session |

- **test-runner** does not invoke test-agent per individual step.
- **test-agent** receives the full step block (Step 1 … Step N) and executes them in order without expecting a follow-up invocation for the same test name.
- `context = {}` is scoped to **one test case invocation** — shared across all steps in that run, reset for the next test name.

---

## Purpose

Execute **all** steps for one test case in a single run. For each step, **read the instruction carefully**, infer what kind of action it requires, and apply the matching protocol below. This project supports only two execution flows:

- `UI` steps via Playwright MCP
- `SQL` steps via `user-oracle-sqlcl` MCP

When **every** step is done (or the test case fails irrecoverably), produce a **self-contained, re-runnable** Python script named `{testcase_name}.py` and return one verdict to test-runner.

---

## Step Instructions — Read Carefully, Infer Type, Apply Rules

**Before executing any step**, read its full instruction text and decide which step type it implies. Steps may be numbered (`Step 1: ...`) or plain prose; an explicit `[UI]` / `[SQL]` tag is optional — **the instruction content is the source of truth**.

### Mandatory per-step workflow

1. **Read** the entire step instruction—do not skim or assume from step number alone.
2. **Infer** the step type (`UI` or `SQL`) from verbs, targets, and technology named in the text.
3. **State** the inferred type briefly in your execution log (e.g. `Step 3 → inferred: SQL`).
4. **Apply** the full rule block for that type from the sections below.
5. If an explicit `[TYPE]` tag is present and it **conflicts** with what the instruction describes, **follow the instruction** and note the mismatch.

Preserve blank lines, comments, and section headers in the step block as-is.

### How to infer step type (implicit classification)

| Inferred type | Instruction usually involves… | Examples |
|---------------|----------------------------------|----------|
| **UI** | Browser, page, screen, login form, button, link, field, dropdown, tab, modal, navigation, click, type/fill, select option, verify text/element on screen | “Log in to FAM”, “Click Submit”, “Select country from dropdown”, “Verify order appears in grid” |
| **SQL** | Database, query, SELECT/INSERT/UPDATE/DELETE, table/column, Oracle, row count, fetch from DB, validate in database | “Run query to get OFFER_ID”, “Verify status in ORDERS table” |

**Disambiguation**

- UI vs SQL: interaction with a **visible application in the browser** → UI; **database query/validation** against Oracle objects → SQL.
- If a single step mixes UI and SQL (e.g. “query DB then click Save”), split into sub-actions and apply each type’s rules in order within that step.
- If a step instruction describes REST/SOAP/BACKEND behavior, treat it as unsupported for this framework and fail the test with a clear `Remark` that the step must be rewritten as UI/SQL.

### UI resume trigger (inferred types)

When the **inferred** type of the current step is **UI** and the **previous** step was inferred as **SQL**, run the **UI Resume Protocol** before any UI action—even if no `[UI]` tag was written.

---

## Inputs (from test-runner via test-agent)

| Input | Required | Purpose |
|--------|----------|---------|
| `testcase_name` | Yes | Output script name, e.g. `TS_001_Order_creation.py` |
| `step_definitions` | Yes | **Complete** step block for one test name — all steps (Step 1 … Step N) in one text block |
| `input_values` | No | Raw `Input Values` cell text — `key - value` lines that fill the `{placeholder}` tokens in the steps |
| `excel_path` | Yes | Source Excel workbook — test-agent writes **Result** and **Remark** here |
| `row_number` | Yes | Excel row for this test name (used for write-back) |
| `db_connection_name` | Yes | Default SQLCL connection name from `.env` key `DB_CONNECTION` (passed by test-runner) |

Use `db_connection_name` as the SQLCL `connection_name` for all SQL steps in the test case.
`ORACLE_DB_*` values in `.env` are environment metadata for validation/traceability; they are not passed to MCP `connect`.

Do not read step definitions from Excel in test-agent — test-runner supplies `step_definitions` verbatim from the step column. test-agent **does** open `excel_path` only to write **Result** and **Remark** for the current test name (via `row_number`).

---

## Global Rules (Always Apply)

### Context Passing

- Initialize `context = {}` once at the start of the test case (one test-agent invocation)
- Store every extracted value (DB output, UI scrape) in `context`
- Read from `context` in later steps within the **same** test case — **never** hardcode values from prior steps
- Example: SQL returns `order_id` → `context["order_id"]` → UI step fills order_id field from context
- Do not carry `context` to a different test name — test-runner starts a fresh test-agent call per row

### Input Value Substitution

- Steps may contain `{placeholder}` tokens (e.g. `{Application URL}`, `{Username}`, `{Transaction Type}`, `{agreement}`)
- Resolve each token from `input_values` by **case-insensitive** key match (`{agreement}` ↔ `Agreement`); parse `input_values` into `key - value` pairs, splitting each line on the first ` - ` only (values may contain `-`, `:`, `//`)
- Seed resolved values into `context` at the start of the test case and read them from `context` in each step
- **Never hardcode** URLs, credentials, or filter values when a matching input is provided — use the input
- If a token has no matching input, log it and proceed with the step's stated value (do not invent one)

### Execution Order

- Run **all** steps in `step_definitions` in order; start at Step 1; finish through the last step in one session
- For **each** step: read instruction → infer type → apply that type’s rules (**mandatory**)
- Return one verdict only after the full test case completes or fails irrecoverably

### Output

- After all steps: compile a complete Python script → `{testcase_name}.py`
- Script must be self-contained and re-runnable
- Capture the screenshots of the results of each test step and put it into screenshots/`{testcase_name}`

---

## UI — UI Protocol (apply when step is inferred as UI)

1. Run `browser_snapshot` **first** — pick selector **from snapshot only**
2. XPath must be stable and unique
3. Perform action via Playwright MCP — **no** raw mouse clicks; use element methods
4. Screenshot to confirm action worked
5. Log action in Python Playwright format

### Page Stabilization

Before interacting on a newly loaded page:

- `page.waitForLoadState('networkidle')` then `page.waitForSelector()` on target with visible/stable check
- If page auto-refreshes: `page.waitForFunction()` to confirm target stays in DOM for at least 2 seconds

### Dropdown Rule

- Never assume `<select>`
- Click trigger → wait for options visible (search **entire** DOM for portals) → select option → confirm closed
- Anchor by label text, placeholder, aria-label, or nearest visible heading — **never** by index or position
- Use `get_by_label()`, `get_by_role("combobox", name="...")`, or label-anchored XPath
- If multiple dropdowns look identical, the **label or field name** is the only reliable anchor

---

## UI Resume Protocol

**When the current step is inferred as UI and the previous step was inferred as SQL** — treat the browser as unknown:

1. Take a **fresh** `browser_snapshot` — do not assume the page is unchanged
2. Verify page state: URL unchanged, no timeout page, no session expiry / login redirect
3. If session expired → re-login and navigate back to the prior screen
4. Stabilize: `page.waitForLoadState('networkidle')` + `page.waitForSelector()` on target
5. Then proceed with the standard UI protocol above

## SQL — Oracle SQLCL MCP Only (apply when step is inferred as SQL)

Do **not** use `DBLibrary.py` or direct DB drivers in test-agent SQL execution. Use `user-oracle-sqlcl` MCP tools only.

### Required SQL execution protocol

1. Resolve `connection_name`:
   - use `db_connection_name` from test-runner (sourced from `.env` `DB_CONNECTION`) with no overrides.
2. Call MCP `connect` with the resolved `connection_name`.
3. Execute query via MCP `run-sql`.
4. Parse returned CSV:
   - Row 1 is header.
   - Build per-column arrays in `context`, e.g. `context["ORDER_ID"] = ["1001", "1002"]`.
   - For single-row results, also store scalar aliases when needed for later placeholders.
5. Log query + compact result snippet.
6. Always call MCP `disconnect` in cleanup/finalization for that DB interaction.

### SQL failure handling

- If `connect` fails: log the `connection_name` and error, then fail the test case.
- If `run-sql` fails: log query + MCP error payload, then fail the test case.
- If CSV parsing fails: log raw SQL output snippet and parser error, then fail the test case.
- If browser session is open during SQL failure, also save a UI screenshot for correlation.

---

## Global Error Handling

**Approach:** Fail quickly, fix quickly.

### UI Failures

- Collect DOM details, screenshots, and failure context
- If element was clicked but no desired result: verify action occurred, single retry after 5 seconds
- Use judgement to fix; log every fix attempt

### DB Failures (Oracle SQLCL MCP)

- Log query + connection/runtime error
- Screenshot current UI state for correlation
- Include SQLCL MCP response snippet and connection name in the failure log

### All Failures

- Dump the full `context` dict to debug log
- Save screenshot of current browser state

---

## Quick Reference

```text
Orchestration: test-runner → one test-agent call per test name → all steps in step_definitions
Per step:      READ instruction carefully → INFER type (UI|SQL) → APPLY matching rules
Context:       context = {} once per test case; no hardcoded cross-step values; reset per test name
UI:            snapshot → selector → Playwright element action → screenshot → log Playwright code
UI after SQL:  UI resume (fresh snapshot, session check, stabilize)
SQL:           user-oracle-sqlcl MCP (connect → run-sql → parse CSV → disconnect)
On failure:    dump context + screenshot; one verdict (no per-step agent re-invocation)
Deliver:       {testcase_name}.py — full test case; screenshots/{testcase_name}/; Result+Remark to excel_path; one verdict
```
