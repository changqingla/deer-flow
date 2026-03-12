---
name: document-format-audit
description: Use this skill when the user uploads .docx/.doc/.pdf documents and asks for format compliance review, naming checks, page/layout checks, font and paragraph checks, heading hierarchy checks, TOC/header/footer/page-number checks, table consistency checks, or language quality review (typos/grammar/punctuation) with a structured audit report.
---

# Document Format Audit Skill

Perform structured document format audits for uploaded office documents.

This skill is designed for compliance-style checks and should be used whenever the user asks to "审核格式", "检查排版", "规范性检查", or similar requests for `.docx`, `.doc`, `.pdf`.

## Workflow

1. Confirm scope and standard:
- Confirm the target file under `/mnt/user-data/uploads/`.
- Confirm whether the user provided a mandatory style standard (font, size, margins, heading rules, naming pattern). If yes, use that as the primary rule set.
- If no explicit standard is provided, use the default checklist in `references/checklist.md`.

2. Run deterministic structural checks:
- For `.docx`, run:
```bash
python /mnt/skills/custom/document-format-audit/scripts/audit_docx.py \
  --file /mnt/user-data/uploads/<filename>.docx \
  --output-json /mnt/user-data/outputs/<filename>.audit.json
```
- If the user specifies a custom naming pattern, pass it with `--filename-rule`:
```bash
python /mnt/skills/custom/document-format-audit/scripts/audit_docx.py \
  --file /mnt/user-data/uploads/<filename>.docx \
  --filename-rule '^[A-Za-z0-9_\\-\\u4e00-\\u9fa5]+-[A-Za-z0-9_\\-\\u4e00-\\u9fa5]+-(\\d{8}|v\\d+(\\.\\d+)*)\\.(docx|doc|pdf)$' \
  --output-json /mnt/user-data/outputs/<filename>.audit.json
```
- For `.doc` and `.pdf`, still run the script; it will produce naming/type checks and explicit "manual required" items for layout-heavy checks.

3. Run content-level language checks:
- Prefer converted markdown files if available (`/mnt/user-data/uploads/<filename>.md`).
- Review:
- obvious typos and awkward sentences
- grammar issues
- punctuation misuse and repeated punctuation
- terminology consistency

4. Generate final audit report:
- Follow `references/report-template.md`.
- Merge deterministic script findings and language review findings.
- Output must include:
- pass/fail/warn/manual status
- evidence (quote, location, or extracted signal)
- fix suggestion
- priority level (high/medium/low)
- final recommendation (pass / conditional pass / fail)

## Important Rules

- Treat script output as ground truth for deterministic fields (filename, extension, parsed layout signals).
- Do not claim strict pass/fail for checks that are not machine-verifiable; mark them as `manual`.
- If the user provides organization-specific standards, override defaults and explicitly state which rules changed.
- If a file is not `.docx`, clearly state capability limits and provide a manual checklist instead of guessing.
- Save reusable outputs to `/mnt/user-data/outputs/` when appropriate.

## Resources

- Audit baseline checklist: `references/checklist.md`
- Report format: `references/report-template.md`
- Deterministic checker: `scripts/audit_docx.py`

> Do not read the Python script source during normal execution; run it directly with parameters.
