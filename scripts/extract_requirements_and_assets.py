#!/usr/bin/env python3
"""从源文件中提取展示任务要求和可用素材。

脚本刻意保持保守，只生成确定性的起点文件，后续由 Codex 复核、分类和细化。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

REQUIREMENT_HINTS = re.compile(
    r"(要求|评分|rubric|criteria|requirement|deliverable|deadline|due|"
    r"presentation|slides?|minutes?|分钟|时长|格式|template|模板|citation|引用|"
    r"must|should|required|禁止|不得|小组|individual|group)",
    re.IGNORECASE,
)
CAPTION_HINTS = re.compile(r"^\s*(图|表|figure|fig\.|table)\s*[\d一二三四五六七八九十IVXivx.\-:：]", re.IGNORECASE)


def q(name: str) -> str:
    prefix, tag = name.split(":")
    return f"{{{NS[prefix]}}}{tag}"


def text_from_xml(el: ET.Element) -> str:
    parts: list[str] = []
    for node in el.iter():
        if node.tag == q("w:t") and node.text:
            parts.append(node.text)
        elif node.tag == q("w:tab"):
            parts.append("\t")
        elif node.tag == q("w:br"):
            parts.append("\n")
    return "".join(parts).strip()


def load_docx_rels(zf: zipfile.ZipFile) -> dict[str, str]:
    rels_path = "word/_rels/document.xml.rels"
    if rels_path not in zf.namelist():
        return {}
    root = ET.fromstring(zf.read(rels_path))
    out: dict[str, str] = {}
    for rel in root.findall("rel:Relationship", NS):
        rid = rel.attrib.get("Id")
        target = rel.attrib.get("Target")
        if rid and target:
            out[rid] = target
    return out


def iter_docx_blocks(path: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    blocks: list[dict[str, Any]] = []
    with zipfile.ZipFile(path) as zf:
        rels = load_docx_rels(zf)
        root = ET.fromstring(zf.read("word/document.xml"))
        body = root.find("w:body", NS)
        if body is None:
            return blocks, rels
        for index, child in enumerate(list(body)):
            if child.tag == q("w:p"):
                style_el = child.find("w:pPr/w:pStyle", NS)
                style = style_el.attrib.get(q("w:val"), "") if style_el is not None else ""
                blips = []
                for blip in child.findall(".//a:blip", NS):
                    rid = blip.attrib.get(q("r:embed"))
                    if rid:
                        blips.append(rid)
                blocks.append(
                    {
                        "kind": "paragraph",
                        "index": index,
                        "text": text_from_xml(child),
                        "style": style,
                        "image_rids": blips,
                    }
                )
            elif child.tag == q("w:tbl"):
                rows: list[list[str]] = []
                for row in child.findall("w:tr", NS):
                    cells = [text_from_xml(cell) for cell in row.findall("w:tc", NS)]
                    rows.append(cells)
                blocks.append({"kind": "table", "index": index, "rows": rows})
    return blocks, rels


def nearest_caption(blocks: list[dict[str, Any]], block_index: int, want_table: bool) -> str:
    labels = ("表", "table") if want_table else ("图", "figure", "fig.")
    candidates: list[tuple[int, str]] = []
    for block in blocks:
        if block.get("kind") != "paragraph":
            continue
        text = block.get("text", "").strip()
        if not text or not CAPTION_HINTS.search(text):
            continue
        lowered = text.lower()
        if any(label in lowered for label in labels):
            candidates.append((abs(block["index"] - block_index), text))
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1] if candidates and candidates[0][0] <= 4 else ""


def write_csv(rows: list[list[str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerows(rows)


def classify_requirement(text: str) -> str:
    lowered = text.lower()
    if text.lstrip().startswith("#"):
        return "topic"
    if re.search(r"^(topic|主题|题目)\s*[:：]", lowered):
        return "topic"
    if re.search(r"(分钟|minutes?|时长|duration|time limit)", lowered):
        return "duration"
    if re.search(r"(rubric|criteria|评分)", lowered):
        return "rubric"
    if re.search(r"(deadline|due|截止)", lowered):
        return "deadline"
    if re.search(r"(deliverable|slides?|ppt|提交|成果|presentation)", lowered):
        return "deliverable"
    if re.search(r"(template|模板|格式|format)", lowered):
        return "format"
    if re.search(r"(citation|引用|reference|参考)", lowered):
        return "citation"
    return "other"


def extract_plain_text(path: Path) -> list[str]:
    if path.suffix.lower() in {".txt", ".md"}:
        return path.read_text(encoding="utf-8", errors="ignore").splitlines()
    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader  # type: ignore
        except Exception:
            return [f"[WARN] 缺少 pypdf，已跳过 PDF 文本抽取：{path}"]
        reader = PdfReader(str(path))
        lines: list[str] = []
        for page_index, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            lines.append(f"# Page {page_index}")
            lines.extend(text.splitlines())
        return lines
    if path.suffix.lower() == ".docx":
        blocks, _ = iter_docx_blocks(path)
        return [block.get("text", "") for block in blocks if block.get("kind") == "paragraph" and block.get("text")]
    return []


def extract_docx_assets(path: Path, outdir: Path, asset_start: int) -> tuple[list[dict[str, Any]], int]:
    assets: list[dict[str, Any]] = []
    figures_dir = outdir / "01-assets" / "figures"
    tables_dir = outdir / "01-assets" / "tables"
    figures_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    blocks, rels = iter_docx_blocks(path)
    with zipfile.ZipFile(path) as zf:
        for block in blocks:
            if block.get("kind") == "paragraph" and block.get("image_rids"):
                for rid in block["image_rids"]:
                    asset_start += 1
                    target = rels.get(rid, "")
                    zip_target = f"word/{target}" if target.startswith("media/") else f"word/media/{Path(target).name}"
                    file_path = ""
                    if zip_target in zf.namelist():
                        suffix = Path(zip_target).suffix or ".bin"
                        dest = figures_dir / f"{path.stem}-figure-{asset_start:03d}{suffix}"
                        dest.write_bytes(zf.read(zip_target))
                        file_path = str(dest)
                    caption = nearest_caption(blocks, block["index"], want_table=False)
                    assets.append(
                        {
                            "asset_id": f"asset-{asset_start:03d}",
                            "source_file": str(path),
                            "source_type": "figure",
                            "source_label": "",
                            "location_hint": f"block {block['index']}",
                            "title_or_caption": caption,
                            "asset_category": "undecided",
                            "deck_use": "undecided",
                            "claim_supported": "",
                            "why_this_asset": "",
                            "speaker_note": "",
                            "file_path": file_path,
                        }
                    )
            elif block.get("kind") == "table":
                asset_start += 1
                dest = tables_dir / f"{path.stem}-table-{asset_start:03d}.csv"
                write_csv(block["rows"], dest)
                caption = nearest_caption(blocks, block["index"], want_table=True)
                assets.append(
                    {
                        "asset_id": f"asset-{asset_start:03d}",
                        "source_file": str(path),
                        "source_type": "table",
                        "source_label": "",
                        "location_hint": f"block {block['index']}",
                        "title_or_caption": caption,
                        "asset_category": "undecided",
                        "deck_use": "undecided",
                        "claim_supported": "",
                        "why_this_asset": "",
                        "speaker_note": "",
                        "file_path": str(dest),
                    }
                )
    return assets, asset_start


def copy_image_assets(path: Path, outdir: Path, asset_start: int) -> tuple[list[dict[str, Any]], int]:
    media_dir = outdir / "01-assets" / "media"
    media_dir.mkdir(parents=True, exist_ok=True)
    asset_start += 1
    dest = media_dir / f"{path.stem}-{asset_start:03d}{path.suffix.lower()}"
    shutil.copy2(path, dest)
    return [
        {
            "asset_id": f"asset-{asset_start:03d}",
            "source_file": str(path),
            "source_type": "image",
            "source_label": "",
            "location_hint": "source file",
            "title_or_caption": path.name,
            "asset_category": "undecided",
            "deck_use": "undecided",
            "claim_supported": "",
            "why_this_asset": "",
            "speaker_note": "",
            "file_path": str(dest),
        }
    ], asset_start


def write_requirements(requirements: list[dict[str, Any]], outdir: Path) -> None:
    req_dir = outdir / "00-requirements"
    req_dir.mkdir(parents=True, exist_ok=True)
    (req_dir / "requirements.json").write_text(json.dumps(requirements, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 任务要求", ""]
    if not requirements:
        lines.append("未检测到明确的任务要求候选项，请人工复核源材料。")
    for item in requirements:
        lines.extend(
            [
                f"## {item['requirement_id']} - {item['requirement_type']}",
                f"- 来源：`{item['source_file']}`",
                f"- 优先级：{item['priority']}",
                f"- 原文：{item['text']}",
                f"- 对 PPT 的影响：{item['presentation_impact']}",
                "",
            ]
        )
    (req_dir / "requirements.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_assets(assets: list[dict[str, Any]], outdir: Path) -> None:
    assets_dir = outdir / "01-assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "assets-index.json").write_text(json.dumps(assets, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# 素材索引", ""]
    if not assets:
        lines.append("未检测到可直接抽取的素材。")
    for asset in assets:
        lines.extend(
            [
                f"## {asset['asset_id']} - {asset['source_type']}",
                f"- 来源：`{asset['source_file']}`",
                f"- 位置：{asset['location_hint']}",
                f"- 标题或图注：{asset['title_or_caption'] or '未检测到'}",
                f"- 素材类别：{asset['asset_category']}",
                f"- 用途判断：{asset['deck_use']}",
                f"- 支撑的观点：{asset['claim_supported']}",
                f"- 文件：`{asset['file_path']}`" if asset.get("file_path") else "- 文件：",
                "",
            ]
        )
    (assets_dir / "assets-index.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="提取展示任务要求和可用素材。")
    parser.add_argument("sources", nargs="+", type=Path)
    parser.add_argument("--outdir", type=Path, default=Path("presentation-prep"))
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    requirements: list[dict[str, Any]] = []
    assets: list[dict[str, Any]] = []
    asset_counter = 0
    req_counter = 0

    for source in args.sources:
        if not source.exists():
            print(f"[WARN] 源文件不存在：{source}", file=sys.stderr)
            continue
        for line in extract_plain_text(source):
            clean = " ".join(line.split())
            if clean and REQUIREMENT_HINTS.search(clean):
                req_counter += 1
                requirements.append(
                    {
                        "requirement_id": f"req-{req_counter:03d}",
                        "source_file": str(source),
                        "requirement_type": classify_requirement(clean),
                        "text": clean,
                        "priority": "unknown",
                        "presentation_impact": "",
                    }
                )
        suffix = source.suffix.lower()
        if suffix == ".docx":
            found, asset_counter = extract_docx_assets(source, args.outdir, asset_counter)
            assets.extend(found)
        elif suffix in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
            found, asset_counter = copy_image_assets(source, args.outdir, asset_counter)
            assets.extend(found)

    write_requirements(requirements, args.outdir)
    write_assets(assets, args.outdir)
    print(f"[OK] 已写入任务要求和素材索引到 {args.outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
