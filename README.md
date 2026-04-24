# pre-skill

`pre-skill` 是一个用于 PPT 前期准备的 Codex skill。它的目标不是直接生成 `.pptx`，而是先完成材料拆解、任务要求提取、展示逻辑分析、逐页大纲、逐页文案、视觉规范、表达边界和平台生成提示词，最终产出一份可交给任意 PPT 生成平台或人工设计师继续制作的中文 PPT 文字底稿。

## 适用场景

- 论文答辩、开题、中期、毕业设计展示
- 课程 presentation、课堂汇报、案例分析、读书报告、小组展示
- 项目汇报、研究分享、商业展示、方案汇报

## 默认产物

默认最终产物是：

```text
07-final-draft/pre-draft.md
```

该底稿包含：

- 群里报题版或提交摘要
- Presentation 统一视觉规范
- 展示主线和页数时间规划
- 主讲页逐页底稿
- 备答页和追问准备
- 图表与素材使用清单
- 图像生成提示词
- 表达边界
- 给 PPT 生成平台的制作指令

`.pptx` 生成是可选后续步骤，仅在用户明确要求“根据底稿生成 PPT”时调用 presentations skill。

## 目录结构

```text
pre-skill/
  SKILL.md
  README.md
  agents/
    openai.yaml
  references/
    output-contract.md
    selection-rules.md
  scripts/
    chunk_sources_and_seed_draft.py
    extract_requirements_and_assets.py
```

## 使用方式

把该目录放入 Codex skills 目录：

```text
C:\Users\<用户名>\.codex\skills\pre-skill
```

然后在 Codex 中提出类似请求：

```text
使用 pre-skill 帮我根据这些课程材料生成 PPT 文字底稿，先不要生成 PPT。
```

或：

```text
使用 pre-skill 拆解论文和图表，生成答辩 PPT 的详细中文文字底稿。
```

## 自动化脚本

### 提取要求和素材

```powershell
python scripts\extract_requirements_and_assets.py <source files> --outdir presentation-prep
```

输出：

- `00-requirements/requirements.md`
- `00-requirements/requirements.json`
- `01-assets/assets-index.md`
- `01-assets/assets-index.json`

### 拆分材料并生成底稿骨架

```powershell
python scripts\chunk_sources_and_seed_draft.py <source files> --outdir presentation-prep --mode course --duration-min 8
```

支持模式：

- `thesis`
- `course`
- `generic`

输出会包含：

- `02-content-chunks/`
- `03-storyline/`
- `04-outline/`
- `05-slide-copy/`
- `06-visual-plan/`
- `07-final-draft/pre-draft.md`

## 工作原则

- 先拆要求和材料，再写展示逻辑。
- 先写逐页底稿，再决定是否生成 PPT。
- 每页只承担一个明确任务。
- 图表必须说明支撑的观点。
- 生成图只能做视觉支持，不能替代事实证据。
- 涉及争议事实、法律判断或专业结论时，必须写表达边界。
