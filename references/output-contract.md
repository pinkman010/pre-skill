# 输出契约

每个 PPT 前期准备项目使用稳定目录结构。默认最终产物是中文 PPT 文字底稿，`.pptx` 仅作为可选后续产物。

```text
presentation-prep/
  00-requirements/
    requirements.md
    requirements.json
  01-assets/
    assets-index.md
    assets-index.json
    figures/
    tables/
    media/
  02-content-chunks/
    source-map.md
    source-map.json
    *.md
  03-storyline/
    presentation-logic.md
    likely-questions.md
  04-outline/
    slides-outline.md
    backup-outline.md
  05-slide-copy/
    slides-script.md
    backup-script.md
  06-visual-plan/
    visual-plan.md
    image-prompts.md
  07-final-draft/
    pre-draft.md
    ppt-platform-prompt.md
    handoff-checklist.md
  08-deck-build/              # 可选：仅在用户明确要求生成 PPTX 时创建
    main-deck.pptx
    backup-deck.pptx
    previews/
```

## 文件用途

所有面向用户的 markdown 内容默认使用中文。JSON 字段名可以保留英文，便于脚本处理。

- `requirements.md`：任务、rubric、时长、听众、格式和约束摘要。
- `requirements.json`：机器可读的任务要求。
- `assets-index.md`：图、表、截图、图表、图片和媒体素材索引。
- `assets-index.json`：机器可读的素材记录。
- `source-map.md`：源文件清单和拆分方式。
- `presentation-logic.md`：展示逻辑 memo，明确主张、证据、取舍和主线。
- `likely-questions.md`：可能追问、追问原因、回答方向和支撑素材。
- `slides-outline.md`：主讲页顺序和每页任务，不写重文案。
- `backup-outline.md`：备答页或附录页顺序。
- `slides-script.md`：逐页可见文案、讲稿重点和转场。
- `backup-script.md`：备答页文字底稿。
- `visual-plan.md`：进入 PPT 生成前的视觉、图表和布局计划。
- `image-prompts.md`：生成图提示词；只有允许生成图时使用。
- `pre-draft.md`：最终 PPT 文字底稿，给用户、设计师或任意 PPT 生成平台使用；结构应接近课程 `pre底稿.md`，包含报题版、统一视觉规范、逐页制作说明、展示建议和表达边界。
- `ppt-platform-prompt.md`：把 `pre-draft.md` 投喂给 PPT 生成平台时的总提示词。
- `handoff-checklist.md`：交付前检查清单，列出缺口、素材、平台限制和后续动作。

## 任务要求字段

每条 requirement 应包含：

- `requirement_id`
- `source_file`
- `requirement_type`：topic、duration、audience、rubric、deliverable、format、citation、forbidden、deadline、template、other
- `text`
- `priority`：must、should、optional、unknown
- `presentation_impact`

## 素材字段

每条 asset 应包含：

- `asset_id`
- `source_file`
- `source_type`：figure、table、chart、screenshot、image、generated-image-plan、other
- `source_label`：例如图 3-2、表 4-1、页面编号
- `location_hint`：章节、页码、段落、幻灯片或表格行
- `title_or_caption`
- `asset_category`
- `deck_use`：main、backup、generated、drop、undecided
- `claim_supported`
- `why_this_asset`
- `speaker_note`
- `file_path`：已抽取到磁盘时填写

## 大纲字段

每页记录应包含：

- `slide_id`
- `deck_type`：main 或 backup
- `title`
- `slide_job`
- `core_point`
- `supporting_asset_ids`
- `requirement_ids`
- `time_budget_sec`

## 逐页底稿字段

每页底稿应包含：

- `slide_id`
- `working_title`
- `subtitle`
- `onscreen_content`
- `page_conclusion`
- `visible_copy`
- `core_message`
- `support_points`
- `presentation_note`
- `recommended_visual_form`
- `asset_layout_note`
- `layout_note`
- `speaker_focus`
- `transition_sentence`
- `time_budget`
- `question_risk`

## 视觉计划字段

每条视觉计划应包含：

- `slide_id`
- `visual_role`：evidence、diagram、chart、table、generated-concept、background、icon、none
- `asset_ids`
- `generation_allowed`：yes 或 no
- `image_prompt`：需要生成图时填写
- `negative_constraints`
- `text_safe_area`

## 最终底稿结构

`07-final-draft/pre-draft.md` 必须使用以下结构：

```markdown
# 主题名称

## Part I. Presentation

### 基本信息与输出假设

### 群里报题版

#### 题目

#### 100-150字简介

### Presentation 统一视觉规范

#### 主题风格

#### 配色建议

#### 字体建议

#### 页面结构建议

#### 元素使用建议

### Slide 1 标题页

#### 页面标题

#### 页面副标题

#### 上屏内容

#### 页面结论

#### 展示建议

#### 推荐呈现方式

#### 版式建议

#### 讲稿要点

#### 转场句

#### 预计讲时

#### 追问风险

### Slide 2 页面标题

按 Slide 1 的字段继续逐页写。

### Presentation 制作与展示建议

#### 视觉呈现建议

#### 标题与信息密度建议

#### 时长控制建议

#### 平台生成注意事项

## Part II. 表达边界

- 事实表述边界：
- 法律或专业判断边界：
- 禁用或慎用表述：
- 可以使用的替代表述：

## Part III. 备答与附录

### 可能追问

### 备答页逐页底稿

### 图表与素材使用清单

### 图像生成提示词

## Part IV. 给 PPT 生成平台的制作指令

## Part V. 待确认事项
```

## 最终底稿字段要求

- `群里报题版`：课程 presentation、课堂汇报、比赛路演等场景必须生成；论文答辩可改为“答辩题目与摘要”。
- `Presentation 统一视觉规范`：必须先约束整套风格，再写逐页版式。
- `Slide N`：每页尽量使用 `页面标题 / 上屏内容 / 页面结论 / 展示建议 / 版式建议`，需要时补 `页面副标题 / 推荐呈现方式 / 讲稿要点 / 收尾句`。
- `Presentation 制作与展示建议`：写给后续 PPT 生成平台或人工排版者，重点控制视觉、密度和时长。
- `表达边界`：涉及争议事实、法律结论、伦理判断、医学金融政策等高风险内容时必须写；普通课程汇报也建议写“不要夸大”的边界。
- `备答与附录`：只放主讲会拖慢节奏、但 Q&A 可能需要的内容。

## 命名规则

- 文件名使用 lowercase kebab-case。
- 默认最终底稿命名为 `pre-draft.md`。
- 用户要求沿用中文文件名时，可以另存为 `pre底稿.md`。
- 稳定路径优先，便于后续自动化消费。
- 在早期阶段未确认前，不覆盖后期文件。
- 需要版本时使用明确后缀，例如 `pre-draft-10min.md`、`pre-draft-course-v2.md`。
