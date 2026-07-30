from __future__ import annotations

import json
import unittest
import urllib.error
from typing import Any

from app.providers.base import ProviderHTTPError, ProviderResponseError
from app.providers.gpt_image import GptImageProvider, request_json
from app.schemas.job import GenerationRequest, PollingConfig, ProviderConfig


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


class QueueOpener:
    def __init__(self, *payloads: dict[str, Any]) -> None:
        self.payloads = list(payloads)
        self.requests: list[Any] = []

    def __call__(self, request: Any, timeout: float) -> FakeResponse:
        self.requests.append(request)
        return FakeResponse(self.payloads.pop(0))


class GptImageProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = ProviderConfig(
            base_url="https://images.example.com/",
            api_key="secret",
            model="gpt-image-2",
        )

    def test_submit_uses_compatible_endpoint_and_payload(self) -> None:
        opener = QueueOpener({"code": 200, "data": [{"task_id": "task_123"}]})
        provider = GptImageProvider(self.config, opener=opener)
        request = GenerationRequest(
            prompt="一只手提包",
            image_urls=("data:image/png;base64,AAAA",),
            official_fallback=True,
        )

        task_id = provider.submit(request)

        self.assertEqual(task_id, "task_123")
        sent_request = opener.requests[0]
        self.assertEqual(
            sent_request.full_url,
            "https://images.example.com/v1/images/generations",
        )
        self.assertEqual(sent_request.get_method(), "POST")
        self.assertEqual(
            json.loads(sent_request.data.decode("utf-8")),
            {
                "model": "gpt-image-2",
                "prompt": "一只手提包",
                "n": 1,
                "size": "3:4",
                "resolution": "1k",
                "official_fallback": True,
                "image_urls": ["data:image/png;base64,AAAA"],
            },
        )

    def test_wait_for_completion_parses_progress_and_images(self) -> None:
        opener = QueueOpener(
            {"code": 200, "data": {"status": "processing", "progress": 30}},
            {
                "code": 200,
                "data": {
                    "status": "completed",
                    "progress": 100,
                    "result": {
                        "images": [
                            {"url": "https://example.com/one.png"},
                            {
                                "url": [
                                    "https://example.com/two.png",
                                    "https://example.com/three.png",
                                ]
                            },
                        ]
                    },
                },
            },
        )
        sleeps: list[float] = []
        updates = []
        provider = GptImageProvider(
            self.config,
            opener=opener,
            sleeper=sleeps.append,
            monotonic=lambda: 0,
        )

        job = provider.wait_for_completion(
            "task_123",
            PollingConfig(initial_delay=10, poll_interval=5, timeout=180),
            on_update=updates.append,
        )

        self.assertTrue(job.is_completed)
        self.assertEqual(
            job.image_urls,
            [
                "https://example.com/one.png",
                "https://example.com/two.png",
                "https://example.com/three.png",
            ],
        )
        self.assertEqual([update.progress for update in updates], [30, 100])
        self.assertEqual(sleeps, [10, 5])
        self.assertIn("/v1/tasks/task_123?language=zh", opener.requests[0].full_url)

    def test_submit_rejects_missing_task_id(self) -> None:
        provider = GptImageProvider(
            self.config,
            opener=QueueOpener({"code": 200, "data": []}),
        )

        with self.assertRaisesRegex(ProviderResponseError, "未找到 task_id"):
            provider.submit(GenerationRequest(prompt="测试"))

    def test_request_json_converts_network_error(self) -> None:
        def failing_opener(request: Any, timeout: float) -> FakeResponse:
            raise urllib.error.URLError("offline")

        with self.assertRaisesRegex(ProviderHTTPError, "offline"):
            request_json(
                "GET",
                "https://images.example.com/task",
                "secret",
                opener=failing_opener,
            )


if __name__ == "__main__":
    unittest.main()
