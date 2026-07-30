from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from app.domain.generation_job import FINAL_STATUSES, RUNNING_STATUSES, GenerationJob
from app.providers.base import ProviderError
from app.providers.gpt_image import (
    GptImageProvider,
    join_url as provider_join_url,
    parse_image_urls,
    request_json as provider_request_json,
)
from app.schemas.job import GenerationRequest, PollingConfig, ProviderConfig


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
ENV_FILE = PROJECT_ROOT / ".env"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"

ApiError = ProviderError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="通过配置的图片生成模型生成图片，并下载到 output 目录。"
    )
    parser.add_argument("prompt", help="图片生成提示词")
    parser.add_argument("--size", default="3:4", help="画面比例或像素尺寸，默认 3:4 竖图")
    parser.add_argument(
        "--resolution",
        default="1k",
        choices=("1k", "2k", "4k"),
        help="分辨率档位，默认 1k",
    )
    parser.add_argument(
        "--n",
        type=int,
        default=1,
        choices=(1,),
        help="生成图片数量，当前接口固定为 1",
    )
    parser.add_argument(
        "--image-url",
        action="append",
        dest="image_urls",
        help="参考图 URL 或 base64 data URI，可重复传入，最多 16 张",
    )
    parser.add_argument(
        "--image-file",
        action="append",
        dest="image_files",
        help="本地参考图路径，会自动转成 base64 data URI，可重复传入",
    )
    parser.add_argument(
        "--official-fallback",
        action="store_true",
        help="请求失败时允许使用官方渠道兜底",
    )
    parser.add_argument(
        "--env",
        default="IMAGE_API_KEY",
        help="读取 API Key 的环境变量名，默认 IMAGE_API_KEY",
    )
    parser.add_argument(
        "--initial-delay",
        type=float,
        default=10,
        help="提交任务后首次查询前等待秒数，默认 10",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=5,
        help="任务轮询间隔秒数，默认 5",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180,
        help="轮询超时时间秒数，默认 180",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="图片保存目录；不传则在 output 下按当前时间创建子文件夹",
    )
    return parser.parse_args()


def request_json(
    method: str,
    url: str,
    api_key: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return provider_request_json(method, url, api_key, payload)


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


def submit_task(args: argparse.Namespace, api_key: str) -> str:
    image_urls = build_image_inputs(args.image_urls, args.image_files)
    request = GenerationRequest(
        prompt=args.prompt,
        size=args.size,
        resolution=args.resolution,
        n=args.n,
        image_urls=tuple(image_urls),
        official_fallback=args.official_fallback,
    )
    return _provider_from_args(args, api_key).submit(request)


def build_image_inputs(
    image_urls: list[str] | None,
    image_files: list[str] | None,
) -> list[str]:
    images = list(image_urls or [])
    images.extend(image_file_to_data_uri(Path(file_path)) for file_path in image_files or [])
    if len(images) > 16:
        raise ApiError("参考图最多支持 16 张")
    return images


def image_file_to_data_uri(path: Path) -> str:
    if not path.exists():
        raise ApiError(f"本地参考图不存在: {path}")
    if not path.is_file():
        raise ApiError(f"本地参考图不是文件: {path}")

    mime_type = mimetypes.guess_type(path.name)[0]
    if mime_type not in {"image/png", "image/jpeg", "image/webp"}:
        raise ApiError("本地参考图仅支持 png、jpg、jpeg、webp")

    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def poll_task(args: argparse.Namespace, api_key: str, task_id: str) -> dict[str, Any]:
    polling = PollingConfig(
        initial_delay=args.initial_delay,
        poll_interval=args.poll_interval,
        timeout=args.timeout,
    )
    job = _provider_from_args(args, api_key).wait_for_completion(
        task_id,
        polling,
        on_update=_print_job_update,
    )
    return dict(job.raw)


def _provider_from_args(
    args: argparse.Namespace,
    api_key: str,
) -> GptImageProvider:
    return GptImageProvider(
        ProviderConfig(
            base_url=args.base_url,
            api_key=api_key,
            model=args.model,
        )
    )


def _print_job_update(job: GenerationJob) -> None:
    progress_text = f", progress={job.progress}%" if job.progress is not None else ""
    print(f"任务状态: {job.status or 'unknown'}{progress_text}", flush=True)
    if job.status and job.status not in RUNNING_STATUSES | FINAL_STATUSES:
        print(f"收到未知状态 {job.status!r}，继续轮询。", flush=True)


def collect_image_urls(task: dict[str, Any]) -> list[str]:
    urls = [image.url for image in parse_image_urls(task)]
    if not urls:
        raise ApiError(f"任务已完成但未找到图片 URL: {json.dumps(task, ensure_ascii=False)}")
    return urls


def download_images(
    urls: list[str],
    task_id: str,
    output_dir: Path = OUTPUT_DIR,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    filename_task_id = task_id_filename_stem(task_id)
    paths: list[Path] = []
    for index, url in enumerate(urls, start=1):
        suffix = suffix_from_url(url) or ".png"
        if suffix == ".jpeg":
            suffix = ".jpg"
        filename = f"{image_filename_stem(url, filename_task_id, index)}{suffix}"
        path = output_dir / filename
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "User-Agent": USER_AGENT,
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                path.write_bytes(response.read())
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            detail = error_body[:300] if error_body else exc.reason
            raise ApiError(f"下载图片失败 {url}: HTTP {exc.code} {detail}") from exc
        except urllib.error.URLError as exc:
            raise ApiError(f"下载图片失败 {url}: {exc.reason}") from exc
        paths.append(path)
    return paths


def task_id_filename_stem(task_id: str) -> str:
    return task_id.removeprefix("task_")


def image_filename_stem(url: str, task_id: str, index: int) -> str:
    stem = Path(urllib.parse.urlparse(url).path).stem
    marker = "task_"
    if marker in stem:
        return stem.rsplit(marker, 1)[1]
    return f"{task_id}_{index - 1}"


def suffix_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    suffix = Path(parsed.path).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return suffix
    return ""


def join_url(base_url: str, path: str) -> str:
    return provider_join_url(base_url, path)


def timestamped_output_dir(base_dir: Path = OUTPUT_DIR) -> Path:
    return base_dir / datetime.now().strftime("%Y%m%d-%H%M%S")


def main() -> int:
    load_dotenv()
    args = parse_args()
    api_key = os.getenv(args.env)
    if not api_key:
        print(f"请先在环境变量或 .env 中设置 {args.env}。", file=sys.stderr)
        return 2
    base_url = os.getenv("IMAGE_BASE_URL")
    if not base_url:
        print("请先在环境变量或 .env 中设置 IMAGE_BASE_URL。", file=sys.stderr)
        return 2
    model = os.getenv("IMAGE_MODEL")
    if not model:
        print("请先在环境变量或 .env 中设置 IMAGE_MODEL。", file=sys.stderr)
        return 2
    args.base_url = base_url
    args.model = model

    try:
        task_id = submit_task(args, api_key)
        print(f"任务已提交: {task_id}", flush=True)
        task = poll_task(args, api_key, task_id)
        urls = collect_image_urls(task)
        paths = download_images(urls, task_id, args.output_dir or timestamped_output_dir())
    except (ApiError, TimeoutError) as exc:
        print(f"错误: {exc}", file=sys.stderr)
        return 1

    print("图片已保存:")
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
