import openpyxl
import re
import json
import sys

path = r"Functional_Test_Cases.xlsx"
wb = openpyxl.load_workbook(path, read_only=True, data_only=True)

sheet = None
for name in wb.sheetnames:
    if name.lower() in ("test cases", "tests"):
        sheet = wb[name]
        break
if sheet is None:
    sheet = wb[wb.sheetnames[0]]

print("SHEET:", sheet.title)
print("SHEETS:", wb.sheetnames)

headers = {}
for col_idx, cell in enumerate(sheet[1], start=1):
    if cell.value:
        headers[str(cell.value).strip().lower()] = col_idx

print("HEADERS:", json.dumps(headers))

test_name_cols = ["test name", "test case name", "testcase", "testcase name", "name"]
step_cols = ["test step", "test steps", "step definition", "step definitions", "steps"]
result_cols = ["result", "status", "test result"]
remark_cols = ["remark", "remarks", "comments", "failure reason"]


def find_col(candidates):
    for c in candidates:
        if c in headers:
            return headers[c]
    for c in candidates:
        for header, col in headers.items():
            if c in header or header in c:
                return col
    return None


test_col = find_col(test_name_cols)
step_col = find_col(step_cols)
result_col = find_col(result_cols)
remark_col = find_col(remark_cols)

print("COLS:", test_col, step_col, result_col, remark_col)

if not test_col or not step_col:
    print("ERROR: missing required columns")
    sys.exit(1)
if not result_col or not remark_col:
    print("ERROR: missing write-back columns")
    sys.exit(1)


def derive_name(name):
    name = str(name).strip()
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    name = re.sub(r"_+", "_", name)
    return name


tests = []
skipped = []
for row_idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
    if all(v is None or str(v).strip() == "" for v in row):
        skipped.append((row_idx, "entire row blank"))
        continue
    test_name = row[test_col - 1] if test_col <= len(row) else None
    steps = row[step_col - 1] if step_col <= len(row) else None
    if not test_name or str(test_name).strip() == "":
        skipped.append((row_idx, "test name empty"))
        continue
    if not steps or str(steps).strip() == "":
        skipped.append((row_idx, "step definition empty"))
        continue
    tests.append(
        {
            "row_number": row_idx,
            "testcase_name": derive_name(test_name),
            "test_name": str(test_name).strip(),
            "step_definitions": str(steps).strip(),
        }
    )

print("SKIPPED:", json.dumps(skipped))
print("TEST_COUNT:", len(tests))
for t in tests:
    print("---TEST---")
    print(json.dumps({"row": t["row_number"], "name": t["testcase_name"], "steps_len": len(t["step_definitions"])}))
    print(t["step_definitions"])
