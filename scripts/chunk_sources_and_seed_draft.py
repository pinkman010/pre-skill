#!/usr/bin/env python3
"""拆分展示源材料，并生成 PPT 文字底稿骨架。"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
}


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


def read_docx_blocks(path: Path) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
        body = root.find("w:body", NS)
        if body is None:
            return blocks
        for child in list(body):
            if child.tag != q("w:p"):
                continue
            style_el = child.find("w:pPr/w:pStyle", NS)
            style = style_el.attrib.get(q("w:val"), "") if style_el is not None else ""
            text = text_from_xml(child)
            if text:
                blocks.append({"text": text, "style": style})
    return blocks


def read_source(path: Path) -> list[dict[str, str]]:
    suffix = path.suffix.lower()
    if suffix == ".docx":
        return read_docx_blocks(path)
    if suffix in {".md", ".txt"}:
        return [{"text": line.rstrip(), "style": "Heading" if line.lstrip().startswith("#") else ""} for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader  # type: ignore
        except Exception:
            return [{"text": f"[WARN] 缺少 pypdf，已跳过 PDF 文本抽取：{path}", "style": ""}]
        reader = PdfReader(str(path))
        blocks: list[dict[str, str]] = []
        for page_index, page in enumerate(reader.pages, start=1):
            blocks.append({"text": f"第 {page_index} 页", "style": "Heading"})
            for line in (page.extract_text() or "").splitlines():
                if line.strip():
                    blocks.append({"text": line.strip(), "style": ""})
        return blocks
    return []


def is_heading(block: dict[str, str]) -> bool:
    text = block["text"].strip()
    style = block.get("style", "").lower()
    if "heading" in style or style.startswith("toc"):
        return True
    if text.startswith("#"):
        return True
    if re.match(r"^(\d+(\.\d+)*|第[一二三四五六七八九十0-9]+[章节部分])\s*[、.．:：]?\s+\S+", text):
        return True
    return len(text) <= 36 and bool(re.search(r"(要求|背景|问题|方法|实验|结果|结论|case|analysis|conclusion|rubric|method|result)", text, re.I))


def split_sections(source: Path, blocks: list[dict[str, str]]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    current = {"title": source.stem, "source": str(source), "paragraphs": []}
    for block in blocks:
        text = block["text"].strip()
        if is_heading(block) and current["paragraphs"]:
            sections.append(current)
            current = {"title": text.lstrip("# ").strip(), "source": str(source), "paragraphs": []}
        elif is_heading(block):
            current["title"] = text.lstrip("# ").strip()
        else:
            current["paragraphs"].append(text)
    if current["paragraphs"] or not sections:
        sections.append(current)
    return sections


def classify_section(title: str, body: str, mode: str) -> str:
    text = f"{title}\n{body}".lower()
    if mode == "thesis":
        rules = [
            ("abstract", r"摘要|abstract"),
            ("background", r"背景|研究现状|related work|introduction"),
            ("problem", r"问题|challenge|gap|motivation"),
            ("method", r"方法|模型|framework|method|approach|system"),
            ("experiment-setup", r"实验设置|dataset|数据集|baseline|setting"),
            ("results", r"结果|result|comparison|ablation|消融"),
            ("limitations", r"不足|局限|limitation|future"),
            ("conclusion", r"结论|conclusion"),
        ]
    elif mode == "course":
        rules = [
            ("assignment-requirements", r"要求|rubric|criteria|评分|deliverable|deadline|presentation"),
            ("course-concepts", r"概念|理论|framework|model|reading|lecture"),
            ("case-facts", r"case|案例|背景|事实|company|situation"),
            ("analysis", r"分析|analysis|argument|discussion|评价"),
            ("evidence", r"data|evidence|quote|引用|材料|source"),
            ("conclusion", r"结论|recommendation|建议|conclusion"),
        ]
    else:
        rules = [
            ("task-requirements", r"要求|rubric|criteria|deliverable|deadline|presentation"),
            ("context", r"背景|context|overview|introduction"),
            ("key-ideas", r"观点|idea|claim|proposal|strategy"),
            ("evidence", r"data|evidence|result|quote|case"),
            ("risks", r"risk|风险|limitation|constraint"),
            ("conclusion", r"结论|next step|conclusion"),
        ]
    for name, pattern in rules:
        if re.search(pattern, text, re.I):
            return name
    return "source-notes"


def append_section(bucket: dict[str, list[dict[str, Any]]], category: str, section: dict[str, Any]) -> None:
    bucket.setdefault(category, []).append(section)


def write_chunks(bucket: dict[str, list[dict[str, Any]]], outdir: Path) -> None:
    chunks_dir = outdir / "02-content-chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    source_lines = ["# 来源映射", ""]
    for category, sections in sorted(bucket.items()):
        lines = [f"# {category}", ""]
        for section in sections:
            source_lines.append(f"- `{section['source']}` -> `{category}` / {section['title']}")
            lines.append(f"## {section['title']}")
            lines.append("")
            lines.extend(section["paragraphs"])
            lines.append("")
        (chunks_dir / f"{category}.md").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    (chunks_dir / "source-map.md").write_text("\n".join(source_lines).rstrip() + "\n", encoding="utf-8")


def slide_count_hint(duration_min: int | None) -> str:
    if duration_min is None:
        return "确认时长后再确定页数。"
    if duration_min <= 7:
        return "建议 5 到 8 页主讲。"
    if duration_min <= 10:
        return "建议 8 到 10 页主讲。"
    if duration_min <= 15:
        return "建议 10 到 14 页主讲。"
    return "建议 12 到 16 页主讲。"


def write_seed_files(outdir: Path, mode: str, duration_min: int | None, bucket: dict[str, list[dict[str, Any]]]) -> None:
    (outdir / "03-storyline").mkdir(parents=True, exist_ok=True)
    (outdir / "04-outline").mkdir(parents=True, exist_ok=True)
    (outdir / "05-slide-copy").mkdir(parents=True, exist_ok=True)
    (outdir / "06-visual-plan").mkdir(parents=True, exist_ok=True)
    (outdir / "07-final-draft").mkdir(parents=True, exist_ok=True)

    categories = ", ".join(sorted(bucket)) if bucket else "未识别"
    logic = f"""# 展示逻辑

- 模式：{mode}
- 时长：{duration_min if duration_min is not None else "未知"} 分钟
- 页数建议：{slide_count_hint(duration_min)}
- 已识别内容块：{categories}

## 核心回答

待补充

## 听众与任务要求

待补充

## 叙事主线

1. 起点：
2. 矛盾：
3. 证据：
4. 落点：

## 进入主讲的内容

待补充

## 放入备答或附录的内容

待补充
"""
    (outdir / "03-storyline" / "presentation-logic.md").write_text(logic, encoding="utf-8")

    questions = """# 可能被问到的问题

| 问题 | 为什么可能被问 | 回答方向 | 支撑材料 |
| --- | --- | --- | --- |
| 待补充 | 待补充 | 待补充 | 待补充 |
"""
    (outdir / "03-storyline" / "likely-questions.md").write_text(questions, encoding="utf-8")

    outline = """# 逐页大纲

| 页码 | 类型 | 标题 | 本页任务 | 核心信息 | 支撑材料 | 对应要求 | 预计讲时 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| S01 | 主讲 | 待补充 | 说明任务 | 待补充 | 待补充 | 待补充 | 待补充 |
"""
    (outdir / "04-outline" / "slides-outline.md").write_text(outline, encoding="utf-8")
    (outdir / "04-outline" / "backup-outline.md").write_text("# 备答大纲\n\n待补充\n", encoding="utf-8")

    script = """# 逐页文字底稿

## S01 - 待补充

- 页面标题：
- 页面副标题：
- 上屏内容：
- 页面结论：
- 页面可见文案：
- 核心信息：
- 支撑点：
- 展示建议：
- 推荐呈现方式：
- 图表或视觉位置：
- 版式建议：
- 讲解重点：
- 转场句：
- 预计讲时：
- 追问风险：
"""
    (outdir / "05-slide-copy" / "slides-script.md").write_text(script, encoding="utf-8")
    (outdir / "05-slide-copy" / "backup-script.md").write_text("# 备答文字底稿\n\n待补充\n", encoding="utf-8")

    visual_plan = """# 视觉计划

| 页码 | 视觉角色 | 素材 ID | 是否允许生成图 | 图像提示词 | 负面约束 | 文字安全区 |
| --- | --- | --- | --- | --- | --- | --- |
| S01 | 待补充 | 待补充 | 否 | 待补充 | 不生成文字 | 待补充 |
"""
    (outdir / "06-visual-plan" / "visual-plan.md").write_text(visual_plan, encoding="utf-8")
    image_prompts = """# 图像生成提示词

只在页面任务和事实证据确定后使用。生成图只做视觉支持，不能作为事实证据。

## 提示词模板

- 页码：
- 用途：
- 模型：可用时使用 imagegen 或 OpenAI image-2
- 画幅比例：
- 提示词：
- 负面约束：
- 文字安全区：
"""
    (outdir / "06-visual-plan" / "image-prompts.md").write_text(image_prompts, encoding="utf-8")

    final_draft = f"""# 待补充主题

## Part I. Presentation

### 基本信息与输出假设

- 展示模式：{mode}
- 展示时长：{duration_min if duration_min is not None else "未知"} 分钟
- 页数建议：{slide_count_hint(duration_min)}
- 已识别内容块：{categories}
- 输出目标：生成可投喂任意 PPT 生成平台的中文文字底稿。
- 听众：
- 评分标准或任务要求：
- 格式限制：

### 群里报题版

#### 题目
待补充

#### 100-150字简介
待补充

### Presentation 统一视觉规范

#### 主题风格
- 待补充，例如：学术汇报、科技治理、商业咨询、课程案例、研究答辩。

#### 配色建议
- 主色：
- 辅色：
- 强调色：
- 不建议使用：

#### 字体建议
- 标题：
- 正文：
- 英文术语与数字：

#### 页面结构建议
- 每页结构：
- 结论位置：
- 留白与信息密度：

#### 元素使用建议
- 图表：
- 图标：
- 分隔线、卡片、箭头：

### 展示主线

1. 起点：
2. 矛盾：
3. 分析或方法：
4. 证据：
5. 结论：

### 页数与时间规划

| 页码 | 类型 | 页面标题 | 页面任务 | 预计讲时 |
| --- | --- | --- | --- | --- |
| S01 | 主讲 | 待补充 | 建立展示任务 | 待补充 |

### Slide 1 标题页

#### 页面标题
待补充

#### 页面副标题
待补充

#### 上屏内容
- 待补充

#### 页面结论
- 待补充

#### 展示建议
- 待补充

#### 推荐呈现方式
- 待补充

#### 版式建议
- 待补充

#### 讲稿要点
- 待补充

#### 转场句
- 待补充

#### 预计讲时
- 待补充

#### 追问风险
- 待补充

### Presentation 制作与展示建议

#### 视觉呈现建议
- 待补充

#### 标题与信息密度建议
- 每页上屏内容建议控制在 3-5 条。
- 每条尽量写成“关键词 + 判断”。

#### 时长控制建议
- 待补充

#### 平台生成注意事项
- 严格按照逐页底稿生成，不新增未经确认的事实、数据或引用。
- 页面可见文案保持简洁，讲稿内容放入备注或演讲者说明。

## Part II. 表达边界

- 事实表述边界：
- 法律或专业判断边界：
- 禁用或慎用表述：
- 可以使用的替代表述：

## Part III. 备答与附录

### 可能追问

| 问题 | 为什么可能被问 | 回答方向 | 支撑材料 |
| --- | --- | --- | --- |
| 待补充 | 待补充 | 待补充 | 待补充 |

### 备答页逐页底稿

#### B01｜待补充

- 对应追问：
- 核心回答：
- 支撑材料：
- 讲解方式：

### 图表与素材使用清单

| 素材 ID | 来源 | 用途 | 放置页面 | 支撑观点 |
| --- | --- | --- | --- | --- |
| 待补充 | 待补充 | 待补充 | 待补充 | 待补充 |

### 图像生成提示词

生成图只用于视觉支持，不能作为事实证据。

| 页码 | 用途 | 模型 | 画幅 | 提示词 | 负面约束 |
| --- | --- | --- | --- | --- | --- |
| 待补充 | 待补充 | imagegen / OpenAI image-2 | 待补充 | 待补充 | 不生成文字，不替代真实证据 |

## Part IV. 给 PPT 生成平台的制作指令

- 语言：中文。
- 页面数量：按“页数与时间规划”执行。
- 视觉风格：按“Presentation 统一视觉规范”执行。
- 每页只保留短文案，讲稿内容放入备注或演讲者说明。
- 图表按“图表与素材使用清单”放置，生成图按“图像生成提示词”创建。
- 不要自行添加未经底稿确认的事实、数据或引用。

## Part V. 待确认事项

- 待确认：
"""
    (outdir / "07-final-draft" / "pre-draft.md").write_text(final_draft, encoding="utf-8")

    platform_prompt = """# PPT 生成平台提示词

请根据 `pre-draft.md` 生成一份中文演示文稿。

## 制作要求

- 严格遵循底稿的页码、页面任务、核心结论和时间规划。
- 严格遵循 `Presentation 统一视觉规范`，保持配色、字体、结论位置和信息密度一致。
- 按每页的 `上屏内容 / 页面结论 / 展示建议 / 版式建议` 生成页面。
- 页面可见文案保持简洁，讲稿内容放入备注或演讲者说明。
- 不新增未经底稿确认的事实、数据、引用或案例。
- 遵守 `表达边界`，不要把争议、指控、初步认定或个案判断写成确定结论。
- 原始图表和证据素材优先于生成图。
- 生成图只用于概念、氛围、场景或章节分隔。
- 备答页与主讲页分开。

## 输入材料

- `07-final-draft/pre-draft.md`
- `01-assets/assets-index.md`
- `06-visual-plan/visual-plan.md`
- `06-visual-plan/image-prompts.md`
"""
    (outdir / "07-final-draft" / "ppt-platform-prompt.md").write_text(platform_prompt, encoding="utf-8")

    checklist = """# 交付检查清单

- [ ] 任务要求、rubric、时长和听众已确认。
- [ ] 群里报题版或提交摘要已生成。
- [ ] Presentation 统一视觉规范已写清。
- [ ] 每个主讲页只有一个页面任务。
- [ ] 每页包含上屏内容、页面结论、展示建议、版式建议、讲稿和预计讲时。
- [ ] 主讲页和备答页已分离。
- [ ] 所有图表素材都有来源和用途说明。
- [ ] 生成图提示词不替代真实证据。
- [ ] 涉及争议事实或专业判断时，表达边界已写清。
- [ ] 给 PPT 生成平台的制作指令已写清。
- [ ] 待确认事项已集中列出。
"""
    (outdir / "07-final-draft" / "handoff-checklist.md").write_text(checklist, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="拆分源材料，并生成 PPT 文字底稿骨架。")
    parser.add_argument("sources", nargs="+", type=Path)
    parser.add_argument("--outdir", type=Path, default=Path("presentation-prep"))
    parser.add_argument("--mode", choices=["thesis", "course", "generic"], default="generic")
    parser.add_argument("--duration-min", type=int, default=None)
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    bucket: dict[str, list[dict[str, Any]]] = {}
    processed: list[dict[str, Any]] = []

    for source in args.sources:
        if not source.exists():
            print(f"[WARN] 源文件不存在：{source}", file=sys.stderr)
            continue
        blocks = read_source(source)
        sections = split_sections(source, blocks)
        for section in sections:
            body = "\n".join(section["paragraphs"])
            category = classify_section(section["title"], body, args.mode)
            append_section(bucket, category, section)
        processed.append({"source": str(source), "sections": len(sections)})

    write_chunks(bucket, args.outdir)
    write_seed_files(args.outdir, args.mode, args.duration_min, bucket)
    (args.outdir / "02-content-chunks" / "source-map.json").write_text(json.dumps(processed, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 已写入内容块和底稿骨架到 {args.outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
