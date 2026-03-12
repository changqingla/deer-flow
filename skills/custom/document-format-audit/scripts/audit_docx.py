#!/usr/bin/env python3
"""Deterministic document format checker for .docx-centric audits.

The script focuses on checks that are reliable to automate without external
dependencies. It emits structured JSON so an LLM can combine these results
with manual language review.
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS = {"w": NS_W, "r": NS_R}

DEFAULT_FILENAME_RULE = r"^[A-Za-z0-9_\-\u4e00-\u9fa5]+-[A-Za-z0-9_\-\u4e00-\u9fa5]+-(\d{8}|v\d+(\.\d+)*)\.(docx|doc|pdf)$"
ALLOWED_EXTENSIONS = {"docx", "doc", "pdf"}


def w_attr(name: str) -> str:
    # 生成 WordprocessingML 命名空间下的属性全名，便于读取 XML 属性。
    return f"{{{NS_W}}}{name}"


def r_attr(name: str) -> str:
    # 生成 relationships 命名空间下的属性全名（常用于 r:id）。
    return f"{{{NS_R}}}{name}"


def twips_to_cm(value: int | None) -> float | None:
    # Word 中常用 twips（1/20 point）作为长度单位，这里统一换算为厘米。
    if value is None:
        return None
    return round(value / 566.929, 2)


def add_check(
    checks: list[dict[str, Any]],
    *,
    item: str,
    status: str,
    severity: str,
    evidence: str,
    suggestion: str,
) -> None:
    # 统一追加结构化检查结果，保证输出 JSON 格式稳定。
    checks.append(
        {
            "item": item,
            "status": status,  # 通过 | 失败 | 警告 | 人工复核
            "severity": severity,  # 高 | 中 | 低 | 信息
            "evidence": evidence,
            "suggestion": suggestion,
        }
    )


def parse_xml(zf: zipfile.ZipFile, member: str) -> ET.Element | None:
    # 从 docx(zip) 包内读取并解析指定 XML，失败时返回 None，避免中断全局流程。
    try:
        data = zf.read(member)
        return ET.fromstring(data)
    except Exception:
        return None


def detect_toc(document_root: ET.Element) -> bool:
    # 通过字段指令检测目录（TOC），覆盖 instrText 和 fldSimple 两种写法。
    for instr_text in document_root.findall(".//w:instrText", NS):
        if (instr_text.text or "").upper().find("TOC") >= 0:
            return True
    for fld in document_root.findall(".//w:fldSimple", NS):
        if (fld.get(w_attr("instr")) or "").upper().find("TOC") >= 0:
            return True
    return False


def detect_heading_level(style_name: str) -> int | None:
    # 从样式名推断标题级别，兼容英文 HeadingN、中文“标题N”和“标题一/二/三”。
    m = re.search(r"heading\s*([1-9])", style_name, flags=re.IGNORECASE)
    if m:
        return int(m.group(1))

    m = re.search(r"标题\s*([1-9])", style_name)
    if m:
        return int(m.group(1))

    cn_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    m = re.search(r"标题\s*([一二三四五六七八九])", style_name)
    if m:
        return cn_map.get(m.group(1))

    return None


def analyze_docx(file_path: Path, checks: list[dict[str, Any]]) -> dict[str, Any]:
    # 汇总结构化信号，供最终 JSON 输出与后续模型/人工复核使用。
    signals: dict[str, Any] = {
        "page": {},
        "headings": {},
        "typography": {},
        "tables": {},
        "language_signals": {},
    }

    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            document_root = parse_xml(zf, "word/document.xml")
            if document_root is None:
                # 核心正文 XML 不可读时，后续检查都不可靠，直接记录高优失败并返回。
                add_check(
                    checks,
                    item="DOCX readable",
                    status="fail",
                    severity="high",
                    evidence="word/document.xml missing or invalid",
                    suggestion="Re-export document as valid .docx and re-audit.",
                )
                return signals

            # 页面设置检查
            sect = document_root.find(".//w:sectPr", NS)
            if sect is not None:
                pg_sz = sect.find("w:pgSz", NS)
                pg_mar = sect.find("w:pgMar", NS)

                page_w = int(pg_sz.get(w_attr("w"))) if pg_sz is not None and pg_sz.get(w_attr("w")) else None
                page_h = int(pg_sz.get(w_attr("h"))) if pg_sz is not None and pg_sz.get(w_attr("h")) else None
                orient = (pg_sz.get(w_attr("orient")) if pg_sz is not None else None) or "portrait"
                if page_w and page_h and page_w > page_h:
                    orient = "landscape"

                margins = {}
                for side in ["top", "bottom", "left", "right"]:
                    if pg_mar is not None and pg_mar.get(w_attr(side)):
                        margins[side] = int(pg_mar.get(w_attr(side)))

                signals["page"] = {
                    "width_twips": page_w,
                    "height_twips": page_h,
                    "width_cm": twips_to_cm(page_w),
                    "height_cm": twips_to_cm(page_h),
                    "orientation": orient,
                    "margins_twips": margins,
                    "margins_cm": {k: twips_to_cm(v) for k, v in margins.items()},
                }

                # A4 纸张检查（以纵向尺寸为参考）
                if page_w is None or page_h is None:
                    add_check(
                        checks,
                        item="Page size",
                        status="manual",
                        severity="medium",
                        evidence="Page size not found in section properties.",
                        suggestion="Review page setup manually in Word.",
                    )
                else:
                    a4_portrait = (11906, 16838)
                    a4_landscape = (16838, 11906)
                    tol = 220
                    is_a4 = (
                        abs(page_w - a4_portrait[0]) <= tol and abs(page_h - a4_portrait[1]) <= tol
                    ) or (
                        abs(page_w - a4_landscape[0]) <= tol and abs(page_h - a4_landscape[1]) <= tol
                    )
                    add_check(
                        checks,
                        item="A4 page size",
                        status="pass" if is_a4 else "warn",
                        severity="medium" if not is_a4 else "info",
                        evidence=f"width={page_w}, height={page_h}, orientation={orient}",
                        suggestion="Use A4 page size unless requirements specify otherwise.",
                    )

                # 页边距范围检查
                if not margins:
                    add_check(
                        checks,
                        item="Margins configured",
                        status="manual",
                        severity="medium",
                        evidence="No margin values detected.",
                        suggestion="Set explicit top/bottom/left/right margins.",
                    )
                else:
                    out_of_range = {k: v for k, v in margins.items() if v < 900 or v > 2000}
                    add_check(
                        checks,
                        item="Margins in typical range",
                        status="pass" if not out_of_range else "warn",
                        severity="low" if not out_of_range else "medium",
                        evidence=f"margins_twips={margins}",
                        suggestion="Keep margins in a consistent range, typically 900–2000 twips.",
                    )
            else:
                add_check(
                    checks,
                    item="Page setup detectability",
                    status="manual",
                    severity="medium",
                    evidence="No section properties found.",
                    suggestion="Review page size/orientation/margins manually.",
                )

            # 目录（TOC）检测
            has_toc = detect_toc(document_root)
            add_check(
                checks,
                item="TOC presence",
                status="pass" if has_toc else "warn",
                severity="low" if has_toc else "medium",
                evidence="TOC field detected in document XML." if has_toc else "No TOC field detected.",
                suggestion="Insert or update TOC if the document standard requires it.",
            )

            # 页眉页脚与页码检测
            rels_root = parse_xml(zf, "word/_rels/document.xml.rels")
            rel_map: dict[str, tuple[str, str]] = {}
            if rels_root is not None:
                # 建立 Relationship 映射：rId -> (类型, 目标路径)。
                for rel in rels_root.findall(".//{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"):
                    rid = rel.get("Id")
                    rtype = rel.get("Type", "")
                    target = rel.get("Target", "")
                    if rid:
                        rel_map[rid] = (rtype, target)

            header_targets: list[str] = []
            footer_targets: list[str] = []
            for ref in document_root.findall(".//w:headerReference", NS):
                rid = ref.get(r_attr("id"))
                if rid and rid in rel_map:
                    header_targets.append(rel_map[rid][1])
            for ref in document_root.findall(".//w:footerReference", NS):
                rid = ref.get(r_attr("id"))
                if rid and rid in rel_map:
                    footer_targets.append(rel_map[rid][1])

            has_header_footer = bool(header_targets or footer_targets)
            add_check(
                checks,
                item="Header/Footer presence",
                status="pass" if has_header_footer else "warn",
                severity="low" if has_header_footer else "medium",
                evidence=f"headers={len(header_targets)}, footers={len(footer_targets)}",
                suggestion="Add header/footer if required by template.",
            )

            def contains_page_field(member_path: str) -> bool:
                # 判断页眉/页脚 XML 中是否包含 PAGE 域，用于识别页码自动字段。
                node = parse_xml(zf, member_path)
                if node is None:
                    return False
                for instr_text in node.findall(".//w:instrText", NS):
                    if (instr_text.text or "").upper().find("PAGE") >= 0:
                        return True
                for fld in node.findall(".//w:fldSimple", NS):
                    if (fld.get(w_attr("instr")) or "").upper().find("PAGE") >= 0:
                        return True
                return False

            page_field_found = False
            for target in header_targets + footer_targets:
                member = f"word/{target}" if not target.startswith("word/") else target
                if member in zf.namelist() and contains_page_field(member):
                    page_field_found = True
                    break

            add_check(
                checks,
                item="Page number field",
                status="pass" if page_field_found else "warn",
                severity="low" if page_field_found else "medium",
                evidence="PAGE field found in header/footer." if page_field_found else "No PAGE field detected in header/footer xml.",
                suggestion="Insert page numbers when required by formatting rules.",
            )

            # 基于段落的信号检测
            paragraphs = document_root.findall(".//w:p", NS)
            heading_levels: list[int] = []
            fonts: list[str] = []
            sizes_pt: list[float] = []
            line_spacing_values: list[int] = []
            first_line_indents: list[int] = []
            text_parts: list[str] = []

            for p in paragraphs:
                # 抽取段落纯文本，供轻量语言信号分析（如重复标点、括号配对）。
                text = "".join((t.text or "") for t in p.findall(".//w:t", NS)).strip()
                if text:
                    text_parts.append(text)

                p_style = p.find("./w:pPr/w:pStyle", NS)
                if p_style is not None and p_style.get(w_attr("val")):
                    level = detect_heading_level(p_style.get(w_attr("val"), ""))
                    if level is not None:
                        heading_levels.append(level)

                spacing = p.find("./w:pPr/w:spacing", NS)
                if spacing is not None and spacing.get(w_attr("line")):
                    # 行距在 OOXML 中通常以 1/240 行或相关内部单位存储，这里仅做一致性统计。
                    try:
                        line_spacing_values.append(int(spacing.get(w_attr("line"))))
                    except ValueError:
                        pass

                ind = p.find("./w:pPr/w:ind", NS)
                if ind is not None and ind.get(w_attr("firstLine")):
                    try:
                        first_line_indents.append(int(ind.get(w_attr("firstLine"))))
                    except ValueError:
                        pass

                rpr = p.find(".//w:r/w:rPr", NS)
                if rpr is not None:
                    rfonts = rpr.find("./w:rFonts", NS)
                    if rfonts is not None:
                        # 优先取 eastAsia（中文字体），其次 ascii/hAnsi（西文字体）。
                        font = rfonts.get(w_attr("eastAsia")) or rfonts.get(w_attr("ascii")) or rfonts.get(w_attr("hAnsi"))
                        if font:
                            fonts.append(font)

                    sz = rpr.find("./w:sz", NS)
                    if sz is not None and sz.get(w_attr("val")):
                        try:
                            sizes_pt.append(int(sz.get(w_attr("val"))) / 2.0)
                        except ValueError:
                            pass

            heading_counts = dict(sorted(Counter(heading_levels).items()))
            signals["headings"] = {"counts_by_level": heading_counts}

            if not heading_levels:
                add_check(
                    checks,
                    item="Heading hierarchy",
                    status="warn",
                    severity="medium",
                    evidence="No heading styles detected (Heading1/2... or 标题1/2...).",
                    suggestion="Apply heading styles for structured documents.",
                )
            else:
                level_jumps = []
                prev = heading_levels[0]
                for lv in heading_levels[1:]:
                    # 标题级别跳跃（如 1->3）通常意味着层级不连续。
                    if lv - prev > 1:
                        level_jumps.append((prev, lv))
                    prev = lv
                add_check(
                    checks,
                    item="Heading hierarchy continuity",
                    status="pass" if not level_jumps else "warn",
                    severity="low" if not level_jumps else "medium",
                    evidence=f"heading_counts={heading_counts}, jumps={level_jumps}",
                    suggestion="Avoid skipped heading levels (e.g., H1 -> H3).",
                )

            def dominant(counter_values: list[Any]) -> tuple[Any | None, float]:
                # 计算“主导值 + 占比”，用于评估格式是否统一。
                if not counter_values:
                    return None, 0.0
                c = Counter(counter_values)
                value, count = c.most_common(1)[0]
                return value, round(count / len(counter_values), 3)

            dom_font, dom_font_ratio = dominant(fonts)
            dom_size, dom_size_ratio = dominant(sizes_pt)
            dom_spacing, dom_spacing_ratio = dominant(line_spacing_values)

            signals["typography"] = {
                "dominant_font": dom_font,
                "dominant_font_ratio": dom_font_ratio,
                "dominant_font_size_pt": dom_size,
                "dominant_font_size_ratio": dom_size_ratio,
                "dominant_line_spacing_raw": dom_spacing,
                "dominant_line_spacing_ratio": dom_spacing_ratio,
                "first_line_indent_count": len([v for v in first_line_indents if v > 0]),
                "first_line_indent_samples": first_line_indents[:20],
            }

            add_check(
                checks,
                item="Font consistency",
                status="pass" if dom_font_ratio >= 0.7 else "warn",
                severity="low" if dom_font_ratio >= 0.7 else "medium",
                evidence=f"dominant_font={dom_font}, ratio={dom_font_ratio}",
                suggestion="Keep body text font consistent unless section-specific style requires variation.",
            )
            add_check(
                checks,
                item="Font size consistency",
                status="pass" if dom_size_ratio >= 0.7 else "warn",
                severity="low" if dom_size_ratio >= 0.7 else "medium",
                evidence=f"dominant_size_pt={dom_size}, ratio={dom_size_ratio}",
                suggestion="Use consistent body font size and reserve size changes for heading levels.",
            )
            if line_spacing_values:
                add_check(
                    checks,
                    item="Line spacing consistency",
                    status="pass" if dom_spacing_ratio >= 0.7 else "warn",
                    severity="low" if dom_spacing_ratio >= 0.7 else "medium",
                    evidence=f"dominant_line_raw={dom_spacing}, ratio={dom_spacing_ratio}",
                    suggestion="Use consistent line spacing in body paragraphs.",
                )
            else:
                add_check(
                    checks,
                    item="Line spacing detectability",
                    status="manual",
                    severity="low",
                    evidence="No explicit line spacing attributes found in paragraph properties.",
                    suggestion="Confirm line spacing manually against template requirements.",
                )

            indent_count = len([v for v in first_line_indents if v > 0])
            add_check(
                checks,
                item="First-line indent usage",
                status="pass" if indent_count > 0 else "warn",
                severity="low" if indent_count > 0 else "medium",
                evidence=f"positive_first_line_indent_count={indent_count}",
                suggestion="Apply first-line indent to body paragraphs if required by standard.",
            )

            # 表格相关检查
            tables = document_root.findall(".//w:tbl", NS)
            inconsistent_rows = 0
            overflow_risk_tables = 0

            writable_width = None
            page = signals.get("page", {})
            if page.get("width_twips") and page.get("margins_twips"):
                left = page["margins_twips"].get("left", 0)
                right = page["margins_twips"].get("right", 0)
                writable_width = max(0, page["width_twips"] - left - right)

            for tbl in tables:
                row_counts = []
                for tr in tbl.findall("./w:tr", NS):
                    row_counts.append(len(tr.findall("./w:tc", NS)))
                # 同一表格不同行列数差异较大时，可能存在结构不一致或误排版。
                if row_counts and (max(row_counts) != min(row_counts)):
                    inconsistent_rows += 1

                if writable_width:
                    grid_cols = []
                    for col in tbl.findall("./w:tblGrid/w:gridCol", NS):
                        raw = col.get(w_attr("w"))
                        if raw:
                            try:
                                grid_cols.append(int(raw))
                            except ValueError:
                                pass
                    if grid_cols and sum(grid_cols) > writable_width + 120:
                        # 表格网格总宽超过可写区域，提示潜在越界风险（带容差）。
                        overflow_risk_tables += 1

            signals["tables"] = {
                "table_count": len(tables),
                "inconsistent_row_tables": inconsistent_rows,
                "overflow_risk_tables": overflow_risk_tables,
            }

            add_check(
                checks,
                item="Table structure consistency",
                status="pass" if inconsistent_rows == 0 else "warn",
                severity="low" if inconsistent_rows == 0 else "medium",
                evidence=f"table_count={len(tables)}, inconsistent_row_tables={inconsistent_rows}",
                suggestion="Ensure each table row uses consistent column structure unless merged-cell design is intentional.",
            )
            add_check(
                checks,
                item="Table overflow risk",
                status="pass" if overflow_risk_tables == 0 else "warn",
                severity="low" if overflow_risk_tables == 0 else "medium",
                evidence=f"overflow_risk_tables={overflow_risk_tables}, writable_width={writable_width}",
                suggestion="Adjust table widths or page layout to avoid right-margin overflow.",
            )

            # 语言信号检查（仅启发式）
            full_text = "\n".join(text_parts)
            repeated_punc = re.findall(r"([，。！？；,.!?])\1{1,}", full_text)
            multi_spaces = re.findall(r" {2,}", full_text)

            brackets = {
                "(": ")",
                "（": "）",
                "[": "]",
                "【": "】",
                "“": "”",
            }
            unbalanced = []
            for left, right in brackets.items():
                # 仅做计数级别的启发式检查，不等价于严格语法解析。
                lc = full_text.count(left)
                rc = full_text.count(right)
                if lc != rc:
                    unbalanced.append(f"{left}{right}:{lc}!={rc}")

            signals["language_signals"] = {
                "repeated_punctuation_count": len(repeated_punc),
                "multi_space_count": len(multi_spaces),
                "unbalanced_pairs": unbalanced,
            }

            add_check(
                checks,
                item="Repeated punctuation",
                status="pass" if len(repeated_punc) == 0 else "warn",
                severity="low" if len(repeated_punc) == 0 else "medium",
                evidence=f"repeated_punctuation_count={len(repeated_punc)}",
                suggestion="Normalize punctuation and remove repeated symbols.",
            )
            add_check(
                checks,
                item="Bracket/quote balance",
                status="pass" if not unbalanced else "warn",
                severity="low" if not unbalanced else "medium",
                evidence="balanced" if not unbalanced else ", ".join(unbalanced),
                suggestion="Review unmatched brackets or quote pairs.",
            )
            add_check(
                checks,
                item="Typos and grammar",
                status="manual",
                severity="medium",
                evidence="Automated structural audit completed; semantic language quality requires model/manual review.",
                suggestion="Run LLM-assisted proofreading on the converted markdown or original text.",
            )

    except zipfile.BadZipFile:
        # 文件不是合法 docx(zip) 包结构。
        add_check(
            checks,
            item="DOCX package integrity",
            status="fail",
            severity="high",
            evidence="File cannot be opened as a valid .docx zip package.",
            suggestion="Re-save the file as .docx from Word and re-run audit.",
        )
    except Exception as exc:
        # 容错兜底：记录解析异常，避免脚本异常退出。
        add_check(
            checks,
            item="DOCX parsing",
            status="manual",
            severity="high",
            evidence=f"Parser error: {type(exc).__name__}: {exc}",
            suggestion="Review file manually or retry with a clean export.",
        )

    return signals


def main() -> int:
    # 命令行入口：解析参数、执行检查并输出 JSON 结果。
    parser = argparse.ArgumentParser(description="Audit document format signals with deterministic checks.")
    parser.add_argument("--file", required=True, help="Path to document file (.docx/.doc/.pdf)")
    parser.add_argument("--filename-rule", default=DEFAULT_FILENAME_RULE, help="Regex for filename compliance check")
    parser.add_argument("--output-json", help="Optional output JSON path")
    args = parser.parse_args()

    file_path = Path(args.file)
    checks: list[dict[str, Any]] = []

    if not file_path.exists():
        print(json.dumps({"error": f"File not found: {file_path}"}, ensure_ascii=False, indent=2))
        return 2

    filename = file_path.name
    ext = file_path.suffix.lower().lstrip(".")

    # 基础检查
    try:
        matched = re.match(args.filename_rule, filename) is not None
    except re.error as exc:
        matched = False
        add_check(
            checks,
            item="Filename rule validity",
            status="fail",
            severity="high",
            evidence=f"Invalid regex: {exc}",
            suggestion="Fix --filename-rule and run again.",
        )

    add_check(
        checks,
        item="File naming convention",
        status="pass" if matched else "warn",
        severity="low" if matched else "medium",
        evidence=f"filename={filename}, rule={args.filename_rule}",
        suggestion="Rename file to match project-unit-date/version pattern if required.",
    )

    extension_ok = ext in ALLOWED_EXTENSIONS
    add_check(
        checks,
        item="Allowed file type",
        status="pass" if extension_ok else "fail",
        severity="info" if extension_ok else "high",
        evidence=f"extension={ext}",
        suggestion="Use one of: docx, doc, pdf.",
    )

    signals: dict[str, Any] = {}

    if ext == "docx":
        # DOCX 提供最完整的结构化检查覆盖。
        signals = analyze_docx(file_path, checks)
    elif ext in {"doc", "pdf"}:
        # doc/pdf 在当前脚本仅支持有限检查，需配合人工或模型复核。
        add_check(
            checks,
            item="Layout-level audit coverage",
            status="manual",
            severity="medium",
            evidence=f"{ext} has limited deterministic parsing in this script.",
            suggestion="Prefer .docx for full structural checks, or run manual visual review.",
        )
        add_check(
            checks,
            item="Typos and grammar",
            status="manual",
            severity="medium",
            evidence="Language quality checks are not deterministic for this file type here.",
            suggestion="Use converted markdown or OCR text for model-assisted proofreading.",
        )

    summary_counter = Counter(c["status"] for c in checks)
    result = {
        "file": str(file_path),
        "filename": filename,
        "file_extension": ext,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
        "summary": {
            "pass": summary_counter.get("pass", 0),
            "fail": summary_counter.get("fail", 0),
            "warn": summary_counter.get("warn", 0),
            "manual": summary_counter.get("manual", 0),
            "total": len(checks),
        },
        "signals": signals,
    }

    output_text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output_json:
        out_path = Path(args.output_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_text, encoding="utf-8")

    print(output_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
