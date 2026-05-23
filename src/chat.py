from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"


class ApiError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="通过配置的对话模型获取回复。")
    parser.add_argument("prompt", help="对话提示词")
    parser.add_argument(
        "--image-url",
        action="append",
        dest="image_urls",
        help="图片 URL 或 base64 data URI，可重复传入",
    )
    parser.add_argument(
        "--image-file",
        action="append",
        dest="image_files",
        help="本地图片路径，会自动转成 base64 data URI，可重复传入",
    )
    return parser.parse_args()


def load_dotenv(path: Path = ENV_FILE) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def request_json(url: str, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise ApiError(f"HTTP {exc.code}: {error_body}") from exc
    except urllib.error.URLError as exc:
        raise ApiError(f"请求失败: {exc.reason}") from exc

    try:
        data = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise ApiError(f"响应不是合法 JSON: {response_body[:500]}") from exc

    if data.get("error"):
        raise ApiError(f"API 返回错误: {json.dumps(data['error'], ensure_ascii=False)}")
    return data


def join_url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def build_image_inputs(
    image_urls: list[str] | None,
    image_files: list[str] | None,
) -> list[str]:
    images = list(image_urls or [])
    images.extend(image_file_to_data_uri(Path(file_path)) for file_path in image_files or [])
    return images


def image_file_to_data_uri(path: Path) -> str:
    if not path.exists():
        raise ApiError(f"本地图片不存在: {path}")
    if not path.is_file():
        raise ApiError(f"本地图片不是文件: {path}")

    mime_type = mimetypes.guess_type(path.name)[0]
    if mime_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise ApiError("本地图片仅支持 png、jpg、jpeg、webp")

    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def build_message_content(prompt: str, images: list[str]) -> str | list[dict[str, Any]]:
    if not images:
        return prompt

    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    content.extend(
        {
            "type": "image_url",
            "image_url": {
                "url": image,
            },
        }
        for image in images
    )
    return content


def chat(
    prompt: str,
    image_urls: list[str] | None,
    image_files: list[str] | None,
    base_url: str,
    api_key: str,
    model: str,
) -> str:
    images = build_image_inputs(image_urls, image_files)
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": build_message_content(prompt, images),
            }
        ],
    }
    data = request_json(join_url(base_url, "/v1/chat/completions"), api_key, payload)
    choices = data.get("choices") or []
    if not choices:
        raise ApiError(f"响应中未找到 choices: {json.dumps(data, ensure_ascii=False)}")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if not isinstance(content, str):
        raise ApiError(f"响应中未找到回复内容: {json.dumps(data, ensure_ascii=False)}")
    return content


def main() -> int:
    load_dotenv()
    args = parse_args()
    base_url = os.getenv("CHAT_BASE_URL")
    if not base_url:
        print("请先在环境变量或 .env 中设置 CHAT_BASE_URL。", file=sys.stderr)
        return 2
    api_key = os.getenv("CHAT_API_KEY")
    if not api_key:
        print("请先在环境变量或 .env 中设置 CHAT_API_KEY。", file=sys.stderr)
        return 2
    model = os.getenv("CHAT_MODEL")
    if not model:
        print("请先在环境变量或 .env 中设置 CHAT_MODEL。", file=sys.stderr)
        return 2

    try:
        reply = chat(args.prompt, args.image_urls, args.image_files, base_url, api_key, model)
    except ApiError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1

    print(reply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
