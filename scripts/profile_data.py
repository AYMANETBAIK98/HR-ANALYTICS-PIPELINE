"""Step 1 - Data profiling: understand the source file BEFORE writing the pipeline.

    docker compose run --rm tools python scripts/profile_data.py

What it does:
  1. Reads the HR export from data/landing/
  2. For every column: type, empty values, distinct values, examples
  3. Runs targeted checks for the usual problems of an HR export
  4. Writes the result to docs/profiling_report.md (and prints a summary)

Everything is read as TEXT on purpose: we want to see the file exactly as
the HR system delivered it, before pandas "helpfully" converts anything.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "landing" / "HRDataset_v14.csv"
REPORT = ROOT / "docs" / "profiling_report.md"

# Columns grouped by business meaning (easier to read than 36 in a row)
FAMILIES = {
    "Identity": ["Employee_Name", "EmpID"],
    "Personal": ["DOB", "Sex", "GenderID", "MaritalDesc", "MaritalStatusID", "MarriedID",
                 "CitizenDesc", "HispanicLatino", "RaceDesc", "State", "Zip"],
    "Job": ["Department", "DeptID", "Position", "PositionID", "ManagerName", "ManagerID", "Salary"],
    "Employment lifecycle": ["DateofHire", "DateofTermination", "Termd", "EmploymentStatus",
                             "EmpStatusID", "TermReason"],
    "Recruitment": ["RecruitmentSource", "FromDiversityJobFairID"],
    "Performance & engagement": ["PerformanceScore", "PerfScoreID", "EngagementSurvey",
                                 "EmpSatisfaction", "SpecialProjectsCount",
                                 "LastPerformanceReview_Date", "DaysLateLast30", "Absences"],
}

# Pairs where the file stores the same information twice (label + numeric code)
LABEL_CODE_PAIRS = [
    ("Department", "DeptID"),
    ("Position", "PositionID"),
    ("ManagerName", "ManagerID"),
    ("EmploymentStatus", "EmpStatusID"),
    ("PerformanceScore", "PerfScoreID"),
    ("MaritalDesc", "MaritalStatusID"),
    ("Sex", "GenderID"),
]

DATE_COLUMNS = ["DOB", "DateofHire", "DateofTermination", "LastPerformanceReview_Date"]
PLACEHOLDERS = {"N/A", "NA", "N/A-StillEmployed", "NULL", "-", "?"}


def guess_type(values: pd.Series) -> str:
    """Guess what a text column really contains."""
    v = values.dropna().str.strip()
    if v.empty:
        return "empty"
    if v.str.fullmatch(r"-?\d+").all():
        return "integer"
    if v.str.fullmatch(r"-?\d+(\.\d+)?").all():
        return "decimal"
    if v.str.fullmatch(r"\d{1,2}/\d{1,2}/\d{2,4}").all():
        return "date (text)"
    return "text"


def profile_columns(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col in df.columns:
        s = df[col]
        rows.append({
            "column": col,
            "type": guess_type(s),
            "empty": int(s.isna().sum()),
            "distinct": int(s.nunique(dropna=True)),
            "examples": " | ".join(s.dropna().unique()[:3]),
        })
    return pd.DataFrame(rows)


def find_issues(df: pd.DataFrame) -> list[tuple[str, str, str]]:
    """Return (column, problem, evidence) for every issue found."""
    issues = []

    # 1. Leading / trailing spaces
    for col in df.columns:
        s = df[col].dropna()
        bad = s[s != s.str.strip()]
        if not bad.empty:
            issues.append((col, "extra spaces around the value",
                           f"{len(bad)} rows, e.g. {bad.iloc[0]!r}"))

    # 2. Dates stored as text, and 2-digit years
    for col in DATE_COLUMNS:
        s = df[col].dropna()
        two_digit = s[s.str.fullmatch(r"\d{1,2}/\d{1,2}/\d{2}")]
        issues.append((col, "date stored as text (US format month/day/year)",
                       f"e.g. {s.iloc[0]!r}"))
        if not two_digit.empty:
            # Python/pandas read 2-digit years 00-68 as 2000-2068 and 69-99 as 1969-1999,
            # so a birth year like '58' would wrongly become 2058
            risky = two_digit[two_digit.str[-2:].astype(int) <= 68]
            issues.append((col, "2-digit year: century is ambiguous",
                           f"{len(two_digit)} rows, {len(risky)} would wrongly become 20xx "
                           f"(e.g. {risky.iloc[0]!r})" if not risky.empty else f"{len(two_digit)} rows"))

    # 3. Fake values used instead of "empty"
    for col in df.columns:
        s = df[col].dropna().str.strip()
        fake = s[s.isin(PLACEHOLDERS)]
        if not fake.empty:
            issues.append((col, "placeholder text instead of an empty value",
                           f"{len(fake)} rows = {fake.iloc[0]!r}"))

    # 3b. Same value written with different upper/lower case ("No" vs "no")
    for col in df.columns:
        s = df[col].dropna().str.strip()
        if s.str.contains(r"[A-Za-z]").any() and s.str.lower().nunique() < s.nunique():
            variants = s[s.str.lower().duplicated(keep=False)].unique()[:4]
            issues.append((col, "same value with different case",
                           f"{s.nunique()} variants for {s.str.lower().nunique()} real values: {list(variants)}"))

    # 3c. Codes with leading zeros (lost if the column is read as a number)
    for col in df.columns:
        s = df[col].dropna().str.strip()
        lead = s[s.str.fullmatch(r"0\d+")]
        if not lead.empty:
            issues.append((col, "leading zero, must stay TEXT (not a number)",
                           f"{len(lead)} rows, e.g. {lead.iloc[0]!r} would become {int(lead.iloc[0])}"))

    # 4. Missing values
    for col in df.columns:
        n = int(df[col].isna().sum())
        if n:
            issues.append((col, "empty values", f"{n} rows"))

    # 5. Label and code that should match 1-to-1
    for label, code in LABEL_CODE_PAIRS:
        pairs = df[[label, code]].dropna().apply(lambda c: c.str.strip()).drop_duplicates()
        labels_with_many_codes = pairs.groupby(label)[code].nunique()
        multi = labels_with_many_codes[labels_with_many_codes > 1]
        issues.append((f"{label} / {code}", "same information stored twice (label + code)",
                       "keep one" if multi.empty else
                       f"and INCONSISTENT: {len(multi)} {label} with several codes, e.g. "
                       f"{multi.index[0]!r} -> {sorted(pairs[pairs[label] == multi.index[0]][code])}"))

    # 6. Duplicate employees
    dup = df["EmpID"].duplicated().sum()
    issues.append(("EmpID", "duplicate employee IDs", f"{dup} duplicates") if dup
                  else ("EmpID", "unique key check", "OK, no duplicates"))

    # 7. Business rule: terminated <=> has a termination date
    termd = df["Termd"].str.strip() == "1"
    has_date = df["DateofTermination"].notna()
    mismatch = int((termd != has_date).sum())
    issues.append(("Termd / DateofTermination", "business rule: terminated <=> termination date",
                   "OK, always consistent" if mismatch == 0 else f"{mismatch} rows break the rule"))

    # 8. Name stored as "Last, First"
    if df["Employee_Name"].str.contains(",").all():
        issues.append(("Employee_Name", "name stored as 'Last, First' in one column",
                       f"e.g. {df['Employee_Name'].iloc[0]!r} -> split into first / last name"))
    return issues


def to_markdown(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(r[c]).replace("|", "/") for c in cols) + " |")
    return "\n".join(lines)


def main() -> None:
    df = pd.read_csv(SOURCE, dtype=str, encoding="utf-8-sig", keep_default_na=False, na_values=[""])
    profile = profile_columns(df)
    issues = find_issues(df)
    real_issues = [i for i in issues if not i[2].startswith("OK")]

    # ---- console summary
    print(f"File   : {SOURCE.name}")
    print(f"Shape  : {len(df)} rows x {len(df.columns)} columns\n")
    for family, cols in FAMILIES.items():
        print(f"{family} ({len(cols)}): {', '.join(cols)}")
    print(f"\n{len(real_issues)} issues found:")
    for col, problem, evidence in real_issues:
        print(f"  - {col:<28} {problem}: {evidence}")

    # ---- markdown report
    REPORT.parent.mkdir(exist_ok=True)
    parts = [
        "# Data profiling report: HRDataset_v14.csv",
        "_Generated by `scripts/profile_data.py`. Do not edit by hand; re-run the script._",
        f"\n**{len(df)} rows x {len(df.columns)} columns**, one row per employee.",
        "\n## Columns by family",
        *[f"- **{fam}**: {', '.join(cols)}" for fam, cols in FAMILIES.items()],
        "\n## Column profile",
        to_markdown(profile),
        f"\n## Issues found ({len(real_issues)})",
        to_markdown(pd.DataFrame(issues, columns=["column", "check", "result"])),
    ]
    REPORT.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"\nFull report written to {REPORT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
