from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from typing import Any

from app.domain.generation_job import GeneratedImage, GenerationJob
from app.providers.base import (
    ImageGenerationProvider,
    JobUpdateCallback,
    ProviderError,
    ProviderHTTPError,
    ProviderResponseError,
)
from app.schemas.job import GenerationRequest, PollingConfig, ProviderConfig


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def join_url(base_url: str, path: str) -> str:
    return base_url.rstrip("/") + "/" + path.lstrip("/")


def request_json(
    method: str,
    url: str,
    api_key: str,
    payload: dict[str, Any] | None = None,
    *,
    opener: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    body = None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    open_request = opener or urllib.request.urlopen
    try:
        with open_request(request, timeout=60) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise ProviderHTTPError(f"HTTP {exc.code}: {error_body}") from exc
    except urllib.error.URLError as exc:
        raise ProviderHTTPError(f"请求失败: {exc.reason}") from exc

    try:
        data = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise ProviderResponseError(f"响应不是合法 JSON: {response_body[:500]}") from exc

    if data.get("code") != 200:
        raise ProviderResponseError(
            f"API 返回错误: {json.dumps(data, ensure_ascii=False)}"
        )
    return data


def parse_image_urls(task: Mapping[str, Any]) -> tuple[GeneratedImage, ...]:
    raw_images = ((task.get("result") or {}).get("images")) or []
    urls: list[str] = []
    for image in raw_images:
        value = image.get("url") if isinstance(image, dict) else None
        if isinstance(value, str):
            urls.append(value)
        elif isinstance(value, list):
            urls.extend(str(item) for item in value if item)
    return tuple(GeneratedImage(url=url) for url in urls)


def parse_job(task_id: str, task: Mapping[str, Any]) -> GenerationJob:
    return GenerationJob(
        task_id=task_id,
        status=str(task.get("status", "")),
        progress=task.get("progress"),
        images=parse_image_urls(task),
        raw=dict(task),
    )


class GptImageProvider(ImageGenerationProvider):
    def __init__(
        self,
        config: ProviderConfig,
        *,
        opener: Callable[..., Any] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config
        self._opener = opener
        self._sleeper = sleeper
        self._monotonic = monotonic

    def _request_json(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return request_json(
            method,
            url,
            self.config.api_key,
            payload,
            opener=self._opener,
        )

    def submit(self, request: GenerationRequest) -> str:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "prompt": request.prompt,
            "n": request.n,
            "size": request.size,
            "resolution": request.resolution,
            "official_fallback": request.official_fallback,
        }
        if request.image_urls:
            payload["image_urls"] = list(request.image_urls)

        url = join_url(self.config.base_url, "/v1/images/generations")
        data = self._request_json("POST", url, payload)
        items = data.get("data") or []
        if not items or not items[0].get("task_id"):
            raise ProviderResponseError(
                "提交成功但未找到 task_id: "
                f"{json.dumps(data, ensure_ascii=False)}"
            )
        return str(items[0]["task_id"])

    def get_job(self, task_id: str) -> GenerationJob:
        query = urllib.parse.urlencode({"language": "zh"})
        url = join_url(
            self.config.base_url,
            f"/v1/tasks/{urllib.parse.quote(task_id)}?{query}",
        )
        data = self._request_json("GET", url)
        task = data.get("data") or {}
        if not isinstance(task, Mapping):
            raise ProviderResponseError(
                f"任务数据格式错误: {json.dumps(data, ensure_ascii=False)}"
            )
        return parse_job(task_id, task)

    def wait_for_completion(
        self,
        task_id: str,
        polling: PollingConfig,
        on_update: JobUpdateCallback | None = None,
    ) -> GenerationJob:
        deadline = self._monotonic() + polling.timeout
        if polling.initial_delay > 0:
            self._sleeper(polling.initial_delay)

        while True:
            job = self.get_job(task_id)
            if on_update is not None:
                on_update(job)

            if job.is_completed:
                return job
            if job.status in {"failed", "cancelled"}:
                raise ProviderError(
                    "任务结束但未成功: "
                    f"{json.dumps(job.raw, ensure_ascii=False)}"
                )
            if self._monotonic() >= deadline:
                raise TimeoutError(
                    f"任务 {task_id} 在 {polling.timeout} 秒内未完成"
                )
            self._sleeper(polling.poll_interval)
