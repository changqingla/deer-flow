# Document Format Audit Checklist

## 1) Base Compliance

- File naming:
- Default pattern: `项目名-单位-日期或版本.扩展名`
- Suggested regex: `^[A-Za-z0-9_\-\u4e00-\u9fa5]+-[A-Za-z0-9_\-\u4e00-\u9fa5]+-(\d{8}|v\d+(\.\d+)*)\.(docx|doc|pdf)$`

- File type:
- Accepted: `.docx`, `.doc`, `.pdf`

## 2) Page and Layout (Primarily .docx)

- Page size:
- A4 preferred (portrait approx `11906 x 16838` twips)

- Orientation:
- Portrait by default unless requirements say landscape

- Margins:
- Must be explicitly defined
- Typical range for checks: 900–2000 twips

## 3) Typography and Paragraphs

- Font:
- Check dominant body font consistency

- Font size:
- Check dominant body size consistency

- First-line indent:
- Check whether body paragraphs are consistently indented when required

- Line spacing:
- Check whether line spacing values are present and mostly consistent

- Heading hierarchy:
- Detect heading levels and level jumps
- Flag missing top-level heading or abnormal jumps (e.g., H1 -> H3)

## 4) Structure Completeness

- TOC:
- Detect TOC field presence in document XML (`TOC`)

- Header/Footer:
- Detect header/footer references in section settings

- Page number:
- Detect `PAGE` field in header/footer xml fields

## 5) Tables and Charts

- Tables:
- Detect count and row column consistency
- Flag inconsistent column count by row (possible table corruption)
- Estimate table width against writable page width for potential overflow risk

- Charts/Images:
- For strict visual overflow checks, prefer manual review or rendering-based checks

## 6) Language Quality

- Deterministic signals:
- Repeated punctuation
- Excessive double spaces
- Obvious bracket/quote imbalance

- LLM-assisted review:
- Typos, grammar, punctuation style, wording smoothness, term consistency
- Must include evidence snippets and actionable fixes

## 7) Decision Policy

- Pass:
- No high-severity failures; only minor warnings

- Conditional pass:
- No blockers, but medium issues require edits

- Fail:
- Any high-severity structural or compliance issue that violates required standards
