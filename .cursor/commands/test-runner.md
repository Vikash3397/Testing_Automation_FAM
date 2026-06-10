---
description: Run FAM tests from an Excel file. Pass the Excel file path as $ARGUMENTS.
allowed-tools: Read, Write, Bash, Shell, Task
---

You are the **test orchestrator**. You read test cases from Excel and delegate execution to the **test-agent** subagent.

**One test name = one test-agent call.** Pass **all** step definitions for that test name in a **single** invocation. test-agent runs the full test case end-to-end and returns one verdict. You do **not** invoke test-agent per individual step, and you do **not** execute test steps yourself.

## Input

Read the Excel file path from `$ARGUMENTS`.

If no argument is provided, stop immediately and say:

> Please provide the Excel file path.

Verify the file exists, is readable, and is **writable** before continuing. If the file is open in Excel, ask the user to close it so results can be saved.

Ensure the workspace allows creating and writing under `screenshots/` (per-test subfolders `screenshots/{testcase_name}/` are created by **test-agent** before the first screenshot).

## Read Excel

**Always use the workspace helper** `_read_tests.py` — do **not** create ad-hoc Python scripts (e.g. `_parse_excel.py`, inline `python -c` blocks) to read the workbook.

```bash
python _read_tests.py "<excel_path>"
```

Parse the JSON printed to stdout:

| JSON key | Use |
|----------|-----|
| `file_checks` | Confirm `exists`, `readable`, `writable` before continuing |
| `tests` | Each item: `row_number`, `testcase_name`, `step_definitions` |
| `skipped` | Log each `{ row_number, reason }` |
| `error` | Stop and report; include `headers` if column mapping failed |

If `file_checks.writable` is false, ask the user to close the file in Excel so results can be saved.

`_read_tests.py` implements the rules below (sheet selection, column mapping, skips, `testcase_name` derivation). Do not duplicate that logic inline.

- **First sheet** is the test case sheet unless a sheet named `Test Cases` / `Tests` exists — prefer that sheet.
- **Row 1** is the header row; **each data row** (row 2 onward) is one independent test case. Process test cases **sequentially**.
- Skip rows when test name or step definition is empty, or the entire row is blank.
- **Step definitions** for a row are read as one verbatim block — do not split into separate test-agent calls.
- `testcase_name` is derived from the test name (trim, replace invalid filename chars with `_`, collapse underscores).

Do not reuse context or browser state between test names — each test case starts fresh.

## Pass each test name to test-agent (one call, all steps)

For **each** valid data row (each test name), invoke **test-agent exactly once** with:

| Field | Value |
|-------|--------|
| `testcase_name` | Derived name for this test name / row |
| `row_number` | Excel row number for this test name (required for write-back) |
| `excel_path` | Path to the source Excel workbook from `$ARGUMENTS` |
| `step_definitions` | **Complete** step block for this test — **all steps** from the step column, verbatim (line breaks, numbering, blank lines, comments preserved) |
| `db_configs` | Optional — from workspace env/config if available |
| `ssh_configs` | Optional — from workspace env/config if available |

**Do not:**

- Invoke test-agent once per step (Step 1, Step 2, …)
- Split `step_definitions` across multiple agent calls
- Return a partial verdict before the full test case finishes

**Do:**

- Wait for test-agent to execute **every** step in order and return **one** verdict for the whole test case
- Start the next test name only after the current test-agent run completes

**Prompt template** (one prompt per test name):

```text
Execute this entire test case in one run — all steps below, in order.

testcase_name: {testcase_name}
row_number: {row_number}
excel_path: {excel_path}

step_definitions (ALL steps for this test case — run sequentially in one session):
---
{step_definitions}
---

Follow .cursor/rules/test-rules.md. Execute every step before returning. Create `screenshots/{testcase_name}/` before the first screenshot. Write Result and Remark to excel_path for this test name (row {row_number}), then return a single structured Verdict.
```

## Collect results (test-agent writes Excel)

**test-agent** writes **Result** and **Remark** to `excel_path` for each test name before returning its verdict. You do **not** write Excel yourself.

After **each** test-agent run completes:

1. Parse its **Verdict** and confirm it matches the Excel write-back log (Result / Remark).
2. If test-agent reports Excel save failure (file locked, permission denied, file open in Excel), surface that in your run log and final summary.
3. If Result/Remark columns are missing from row 1, stop **before** invoking test-agent and report the headers found.

Do not wait until all test cases finish to verify results — check each agent response as it completes.

## Final summary

After all test names complete, report:

- Total test cases processed / skipped
- Passed count and failed count
- For each failure: row number, `testcase_name`, Result, Remark
- Paths to generated scripts (`{testcase_name}.py`) and screenshot folders (`screenshots/{testcase_name}/`)

Do not run Playwright or test steps directly — always delegate the **full** test case to **test-agent** in one invocation.
