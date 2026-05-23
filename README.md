# ito-image

用配置的图片生成模型异步接口生成图片，并把结果下载到当前项目的 `output/` 目录。

## 使用

先在同目录 `.env` 中设置 API Key、API Base URL 和模型：

```bash
IMAGE_BASE_URL="https://api.apimart.ai"
IMAGE_API_KEY="你的生图接口密钥"
IMAGE_MODEL="gpt-image-2"

CHAT_BASE_URL="你的对话接口 Base URL"
CHAT_API_KEY="你的对话接口密钥"
CHAT_MODEL="你的对话模型"
```

对话：

```bash
uv run chat "你好，介绍一下你自己"
```

带图片对话：

```bash
uv run chat "描述这张图" --image-file ./input.png
uv run chat "这张图里有什么？" --image-url "https://example.com/image.png"
```

生成一张默认 `3:4` 竖图、`1k` 的图片：

```bash
uv run image "星空下的古老城堡"
```

命令行参数里只有 `prompt` 是必填项，其他参数都可以省略。

会提交以下参数：

```json
{
  "model": "IMAGE_MODEL 环境变量的值",
  "prompt": "你输入的提示词",
  "n": 1,
  "size": "3:4",
  "resolution": "1k",
  "official_fallback": false
}
```

生成完成后，图片会保存到同目录的 `output/` 文件夹。

批量生成多张图时，先在 `output/` 下创建一个本次专属文件夹，然后每次调用 `uv run image` 都传入同一个 `--output-dir`。例如生成 9 张图，就是同一个文件夹里 9 张图。

```bash
RUN_DIR="output/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RUN_DIR"
uv run image "第一张图片提示词" --image-file ./input.png --output-dir "$RUN_DIR"
uv run image "第二张图片提示词" --image-file ./input.png --output-dir "$RUN_DIR"
```

生成 2K 横图：

```bash
uv run image "赛博朋克夜景，雨后的霓虹街道" --size 16:9 --resolution 2k
```

使用本地参考图：

```bash
uv run image "参考这张图的构图，画成水彩风格" --image-file ./input.png
```

常用参数：

```text
prompt              必填，图片生成提示词
--size              画面比例或像素尺寸，默认 3:4 竖图
--resolution        1k / 2k / 4k，默认 1k
--n                 生成数量，当前接口固定为 1
--image-url         参考图 URL 或 base64 data URI，可重复传入
--image-file        本地参考图路径，会自动转成 base64 data URI，可重复传入
--official-fallback 请求失败时允许使用官方渠道兜底
--timeout           轮询超时时间秒数，默认 180
--output-dir        图片保存目录；不传则在 output 下按当前时间创建子文件夹
```
