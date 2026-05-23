---
name: product-image-generation
description: 当用户要求生图、生成图片、产品图、模特产品图、商品场景图或穿搭大片时使用。Use this skill for ITO product image generation: select local product/color/model assets, reverse reference style, write English prompts, and run uv chat/image commands.
---

# Product Image Generation

用于 ITO 产品场景图生成。只使用项目内现有命令，不新写编排脚本，不调用外部生图工具。

```bash
uv run chat "提示词" --image-file "参考图1" --image-file "参考图2"
uv run save-prompts --run-dir "output/<本次运行时间>/" reverse "反推提示词"
uv run save-prompts --run-dir "output/<本次运行时间>/" image "生图提示词1" "生图提示词2"
uv run image "英文生图提示词" --image-file "模特图" --image-file "产品图1" --image-file "产品图2" --output-dir "output/<本次运行时间>/"
```

## Key Rule

- 用户说的数量记为“请求张数”；未指定时默认请求张数为 9。
- 每 1 个请求张数生成 1 条英文生图提示词；每条最终提示词出 4 张图。
- 实际输出图片数 = 请求张数 × 4。例如用户说 9 张，就生成 9 条提示词，最终输出 36 张。
- 警告：每条最终提示词必须执行 4 次 `uv run image`；不要用传入批量数量参数的方式一次生成 4 张。
- `uv run chat` 生成的 JSON 数组长度等于请求张数。
- 反推提示词和生图提示词生成后，立即用 `uv run save-prompts` 记录。
- 单次 `uv run image` 失败时不排查、不重试；记录失败并等待其他任务完成。

## Source Layout

- 产品颜色目录：`source/产品/<产品名>/<颜色名>/`
- 产品描述：`source/产品/<产品名>.md`
- 模特图片：`source/模特/<模特名>.<jpg|jpeg|png|webp>`
- 模特描述：`source/模特/<模特名>.md`
- 参考图：`source/参考图/`

产品图使用所选颜色目录下的全部图片；正面图用于重点识别，扩展名以实际文件为准。

## Workflow

开始工作时先创建本次共享输出目录，后续保存提示词和生图都使用同一个 `$RUN_DIR`：

```bash
RUN_DIR="output/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RUN_DIR"
```

### 1. 本地选择素材

先读取 `source/产品`、`source/模特`、`source/参考图`，不要凭记忆猜产品、颜色、模特或尺寸。

- 产品候选来自 `source/产品/<产品名>/`。
- 颜色候选来自 `source/产品/<产品名>/<颜色名>/`。
- 模特候选来自模特图片文件和同名 `.md` 描述。
- 产品长宽高必须从产品 `.md` 提取。
- 人物身高必须从模特 `.md` 提取。

如果产品尺寸或人物身高缺失，暂停并要求用户补全对应描述文档。

匹配规则：

- 用用户原话做本地确定性匹配，优先完整匹配产品名、颜色名、模特名，再做去空格、大小写不敏感的包含匹配。
- 只匹配到 1 个产品、1 个颜色、1 个模特时直接继续。
- 产品、颜色或模特无法唯一确定时，暂停并用中文列出候选让用户选择；不要猜。
- 如果只确定了产品但未确定颜色，只问颜色。

### 2. 反推参考图风格

读取 `source/参考图` 图片，按文件名排序，最多选 5 张给 `uv run chat`。发送前检查文件大小和像素尺寸：

- 超过 500KB，或宽/高任一边超过 1200px 时，先压缩/缩放。
- 不覆盖原图；压缩图保存到 `source/参考图/_compressed/`，沿用原文件名并输出为 `.jpg`。

```bash
ffmpeg -y -i "原图路径" -vf "scale='min(1200,iw)':'min(1200,ih)':force_original_aspect_ratio=decrease" -q:v 5 "source/参考图/_compressed/原文件名.jpg"
```

如果压缩后仍超过 500KB，逐步提高到 `-q:v 7`、`-q:v 9`，直到不超过 500KB 且最长边不超过 1200px。

让 `uv run chat` 只输出一套英文 `style-only reverse prompt`：描述摄影、构图、镜头、光线、色彩、材质、后期调性和商业大片气质；不要绑定具体人物、产品、品牌、固定物件或可读文字。

生成反推提示词后，立即写入提示词记录文件：

```bash
uv run save-prompts --run-dir "$RUN_DIR" reverse "style-only reverse prompt"
```

### 3. 生成英文生图提示词

调用 `uv run chat` 生成 JSON 数组，长度等于请求张数。不要单独反推或生成服装提示词；服装、造型、姿态或场景变化直接写进每条提示词。

传入上下文：

- 第 2 步的英文 `style-only reverse prompt`。
- 所选产品颜色目录下的正面图和其他产品图。
- 所选模特图片。
- 产品描述 `.md` 和模特描述 `.md` 文本。
- 已提取的产品长宽高和人物身高仅用于后续拼接，不要求 `uv run chat` 写入提示词。

每条英文生图提示词必须包含：

- 指定模特、指定产品、指定颜色。
- 必要的服装、造型、姿态或场景设定。
- 保持产品外形、结构、比例、颜色、材质、五金、缝线、肩带/提手、开口等可见细节。
- 不猜想、不简化、不重设计产品轮廓和结构。
- 透视、接触点、镜头角度、阴影、反射和场景深度自然一致，避免漂浮、贴合错误或透视错位。
- 不添加海报式文字、标题字、宣传语、字幕、水印、UI 或装饰性文字覆盖层；场景自然文字和产品已有文字可以出现。

提示词之间共享参考图调性，但场景、姿态、构图或创意方向要有差异。

拿到生图提示词后，先在每条提示词末尾机械拼接模特身高和产品三维信息，再用于记录和生图。不要让 `uv run chat` 自己生成或改写这些尺寸信息。

拼接格式：

```text
 Model height: <模特身高>. Product dimensions: <产品长宽高>. Use these real measurements to keep the product scale accurate on the model.
```

生成拼接后的最终提示词后，立即追加到提示词记录文件：

```bash
uv run save-prompts --run-dir "$RUN_DIR" image "prompt 1" "prompt 2" "prompt 3"
```

### 4. 提交生图任务

对第 3 步拼接尺寸信息后的每条最终英文提示词出 4 张图：

```bash
uv run image "第 N 条最终英文生图提示词" \
  --image-file "source/模特/<模特名>.<ext>" \
  --image-file "source/产品/<产品名>/<颜色名>/正面.<ext>" \
  --image-file "source/产品/<产品名>/<颜色名>/其他产品图.<ext>" \
  --output-dir "$RUN_DIR"
```

执行要求：

- 每条最终提示词出 4 张图，也就是对同一条提示词执行 4 次 `uv run image`。
- 禁止用传入批量数量参数的方式一次生成 4 张。
- 每次都带上 1 张模特图和所选产品颜色目录下的所有产品图。
- 可以并行发起多个 `uv run image`。
- 所有成功图片保存到同一个 `$RUN_DIR`。
- 文件名优先使用下载 URL 中 `task_` 后面的部分，并去掉冗余前缀。例如 `...gpt_image_2_backup_task_01KSA4B6XHMHRP3Q9FRBCEC88W_0.png` 保存为 `01KSA4B6XHMHRP3Q9FRBCEC88W_0.png`。

### 5. 回复用户

用中文简洁说明：

- 已选择的产品、颜色、模特。
- 请求张数、计划输出图片数，以及实际成功/失败数量。
- 图片保存位置，例如 `output/20260523-153012/`。
- 如果有失败，只列失败序号或简短原因，不展开排查。
