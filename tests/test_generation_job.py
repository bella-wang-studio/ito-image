from __future__ import annotations

import unittest

from app.domain.generation_job import GeneratedImage, GenerationJob
from app.schemas.job import GenerationRequest, PollingConfig, ProviderConfig


class GenerationJobTests(unittest.TestCase):
    def test_status_is_normalized_and_urls_are_exposed(self) -> None:
        job = GenerationJob(
            task_id="task_1",
            status="COMPLETED",
            progress=100,
            images=(GeneratedImage("https://example.com/result.png"),),
        )

        self.assertTrue(job.is_terminal)
        self.assertTrue(job.is_completed)
        self.assertEqual(job.image_urls, ["https://example.com/result.png"])

    def test_unknown_status_is_not_terminal(self) -> None:
        job = GenerationJob(task_id="task_1", status="queued_elsewhere")

        self.assertFalse(job.is_running)
        self.assertFalse(job.is_terminal)


class JobSchemaTests(unittest.TestCase):
    def test_generation_request_keeps_compatible_defaults(self) -> None:
        request = GenerationRequest(prompt="测试")

        self.assertEqual(request.size, "3:4")
        self.assertEqual(request.resolution, "1k")
        self.assertEqual(request.n, 1)
        self.assertFalse(request.official_fallback)

    def test_generation_request_rejects_more_than_16_images(self) -> None:
        with self.assertRaisesRegex(ValueError, "最多支持 16 张"):
            GenerationRequest(
                prompt="测试",
                image_urls=tuple(f"https://example.com/{index}.png" for index in range(17)),
            )

    def test_config_rejects_invalid_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "api_key"):
            ProviderConfig(base_url="https://example.com", api_key="", model="model")
        with self.assertRaisesRegex(ValueError, "poll_interval"):
            PollingConfig(poll_interval=-1)


if __name__ == "__main__":
    unittest.main()
