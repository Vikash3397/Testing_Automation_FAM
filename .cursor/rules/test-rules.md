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

Execute **all** steps for one test case in a single run. For each step, **read the instruction carefully**, infer what kind of action it requires, and apply the matching protocol below. Use Playwright MCP for UI work and the appropriate libraries for non-UI work. When **every** step is done (or the test case fails irrecoverably), produce a **self-contained, re-runnable** Python script named `{testcase_name}.py` and return one verdict to test-runner.

---

## Step Instructions — Read Carefully, Infer Type, Apply Rules

**Before executing any step**, read its full instruction text and decide which step type it implies. Steps may be numbered (`Step 1: …`) or plain prose; an explicit `[UI]` / `[REST]` tag is optional—**the instruction content is the source of truth**.

### Mandatory per-step workflow

1. **Read** the entire step instruction—do not skim or assume from step number alone.
2. **Infer** the step type (`UI`, `REST`, `SQL`, `SOAP`, or `BACKEND`) from verbs, targets, and technology named in the text.
3. **State** the inferred type briefly in your execution log (e.g. `Step 3 → inferred: SQL`).
4. **Apply** the full rule block for that type from the sections below.
5. If an explicit `[TYPE]` tag is present and it **conflicts** with what the instruction describes, **follow the instruction** and note the mismatch.

Preserve blank lines, comments, and section headers in the step block as-is.

### How to infer step type (implicit classification)

| Inferred type | Instruction usually involves… | Examples |
|---------------|----------------------------------|----------|
| **UI** | Browser, page, screen, login form, button, link, field, dropdown, tab, modal, navigation, click, type/fill, select option, verify text/element on screen | “Log in to FAM”, “Click Submit”, “Select country from dropdown”, “Verify order appears in grid” |
| **REST** | HTTP/REST API, endpoint, GET/POST/PUT/PATCH/DELETE, JSON request/response, status code, bearer token, `requests/` payload file | “POST to `/api/orders`”, “Call REST service with body from `requests/create_order.json`” |
| **SQL** | Database, query, SELECT/INSERT/UPDATE/DELETE, table/column, Oracle, row count, fetch from DB, validate in database | “Run query to get OFFER_ID”, “Verify status in ORDERS table” |
| **SOAP** | SOAP, WSDL, XML envelope, operation name, zeep, SOAP endpoint | “Invoke CreateOrder SOAP operation”, “Send XML to billing service” |
| **BACKEND** | SSH, remote server, shell/CLI on host, log file on server, grep/tail on machine, execute command on app server | “SSH to app server and run `grep` in log”, “Restart service via command line on host” |

**Disambiguation**

- UI vs REST: interaction with a **visible application in the browser** → UI; **programmatic HTTP call** with no browser action → REST.
- SQL vs BACKEND: **structured query against a database** → SQL; **OS-level command or log inspection on a host** → BACKEND.
- REST vs SOAP: **JSON/REST endpoint** → REST; **SOAP/XML/WSDL** → SOAP.
- If a single step mixes types (e.g. “query DB then click Save”), split mentally into sub-actions and apply each type’s rules in order within that step.

### UI resume trigger (inferred types)

When the **inferred** type of the current step is **UI** and the **previous** step was inferred as **SQL**, **REST**, **SOAP**, or **BACKEND**, run the **UI Resume Protocol** before any UI action—even if no `[UI]` tag was written.

---

## Inputs (from test-runner via test-agent)

| Input | Required | Purpose |
|--------|----------|---------|
| `testcase_name` | Yes | Output script name, e.g. `TS_001_Order_creation.py` |
| `step_definitions` | Yes | **Complete** step block for one test name — all steps (Step 1 … Step N) in one text block |
| `excel_path` | Yes | Source Excel workbook — test-agent writes **Result** and **Remark** here |
| `row_number` | Yes | Excel row for this test name (used for write-back) |
| `db_configs` | No | DB env mappings, e.g. `sbx1_oracle: user/pass@host:port/service` |
| `ssh_configs` | No | SSH mappings, e.g. `sbx1-app01: user/pass@host` |

If configs are provided, use them for inferred SQL / BACKEND steps instead of inventing credentials.

Do not read step definitions from Excel in test-agent — test-runner supplies `step_definitions` verbatim from the step column. test-agent **does** open `excel_path` only to write **Result** and **Remark** for the current test name (via `row_number`).

---

## Global Rules (Always Apply)

### Context Passing

- Initialize `context = {}` once at the start of the test case (one test-agent invocation)
- Store every extracted value (API, DB, UI scrape, backend output) in `context`
- Read from `context` in later steps within the **same** test case — **never** hardcode values from prior steps
- Example: API returns `order_id` → `context["order_id"]` → UI step fills order_id field from context
- Do not carry `context` to a different test name — test-runner starts a fresh test-agent call per row

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

**When the current step is inferred as UI and the previous step was inferred as SQL, REST, SOAP, or BACKEND** — treat the browser as unknown:

1. Take a **fresh** `browser_snapshot` — do not assume the page is unchanged
2. Verify page state: URL unchanged, no timeout page, no session expiry / login redirect
3. If session expired → re-login and navigate back to the prior screen
4. Stabilize: `page.waitForLoadState('networkidle')` + `page.waitForSelector()` on target
5. Then proceed with the standard UI protocol above

---

## REST (apply when step is inferred as REST)

- Use the `requests` library
- Load body from `requests/<filename>.json` or `.xml` in workspace
- Replace placeholders with `context` values before sending
- Log: method, URL, status code, response snippet
- Retry once on 5xx or timeout; on failure log full request + response
- Store required response values in `context`

---

## SQL — DBLibrary Only (apply when step is inferred as SQL)

Do **not** use raw cx_Oracle. Use [DBLibrary.py](../Keywords/DBLibrary.py).

```python
from Keywords.DBLibrary import DBLibrary

db = DBLibrary(
    username="<DB_USER>",
    password="<DB_PASS>",
    hostname="<DB_HOST>",
    port="<DB_PORT>",
    servicename="<DB_SERVICE>",
)
result = db.ExecuteDB(query)
# result: {"COL_NAME": [val1, val2, ...]}
context["key"] = result["COL_NAME"][0]
```

- `ExecuteDB()` handles connect, query, and close
- Log: query + result snippet
- On error: log query + exception; screenshot UI if browser session is open

---

## SOAP (apply when step is inferred as SOAP)

- Use `zeep` or raw `requests` with XML body from `requests/` folder
- Replace placeholders with `context` values before sending
- Parse response XML; store needed values in `context`
- Log: WSDL, operation, response snippet

---

## BACKEND — SSHLibrary Only (apply when step is inferred as BACKEND)

Do **not** use raw paramiko. Use [SSHLibrary.py](../Keywords/SSHLibrary.py).

```python
from Keywords.SSHLibrary import SSHLibrary

ssh = SSHLibrary(
    hostname="<HOST>",
    username="<SSH_USER>",
    password="<SSH_PASS>",
)
ssh.connect()
output = ssh.execute_command(command)
ssh.close()
```

- `output` is raw stdout — parse and store required values in `context`
- Log: host, command, output snippet
- On error: log command + exception; if `connect()` fails, log host and user

---

## Global Error Handling

**Approach:** Fail quickly, fix quickly.

### UI Failures

- Collect DOM details, screenshots, and failure context
- If element was clicked but no desired result: verify action occurred, single retry after 5 seconds
- Use judgement to fix; log every fix attempt

### API Failures (REST / SOAP)

- Retry once on 5xx or timeout
- On failure: log full request + response

### DB Failures (DBLibrary)

- Log query + connection error
- Screenshot current UI state for correlation
- If `ExecuteDB` raises, catch and log the returned error string

### Backend/SSH Failures (SSHLibrary)

- Log host + command + error
- If `connect()` fails, log connection details (host, user)
- If `execute_command()` raises, catch and log output so far

### All Failures

- Dump the full `context` dict to debug log
- Save screenshot of current browser state

---

## Quick Reference

```text
Orchestration: test-runner → one test-agent call per test name → all steps in step_definitions
Per step:      READ instruction carefully → INFER type (UI|REST|SQL|SOAP|BACKEND) → APPLY matching rules
Context:       context = {} once per test case; no hardcoded cross-step values; reset per test name
UI:            snapshot → selector → Playwright element action → screenshot → log Playwright code
UI after inferred non-UI: UI resume (fresh snapshot, session check, stabilize)
SQL:           DBLibrary.ExecuteDB
BACKEND:       SSHLibrary.execute_command
REST/SOAP:     payloads in requests/; context placeholders; retry 5xx once
On failure:    dump context + screenshot; one verdict (no per-step agent re-invocation)
Deliver:       {testcase_name}.py — full test case; screenshots/{testcase_name}/; Result+Remark to excel_path; one verdict
```
