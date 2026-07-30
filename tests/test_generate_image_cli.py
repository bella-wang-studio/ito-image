from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src import generate_image


class GenerateImageCliTests(unittest.TestCase):
    def test_parse_args_keeps_existing_defaults(self) -> None:
        with patch.object(sys, "argv", ["image", "测试提示词"]):
            args = generate_image.parse_args()

        self.assertEqual(args.prompt, "测试提示词")
        self.assertEqual(args.size, "3:4")
        self.assertEqual(args.resolution, "1k")
        self.assertEqual(args.n, 1)
        self.assertEqual(args.initial_delay, 10)
        self.assertEqual(args.poll_interval, 5)
        self.assertEqual(args.timeout, 180)

    def test_local_image_is_converted_to_data_uri(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "reference.png"
            image_path.write_bytes(b"\x89PNG\r\n")

            images = generate_image.build_image_inputs(
                ["https://example.com/reference.jpg"],
                [str(image_path)],
            )

        self.assertEqual(images[0], "https://example.com/reference.jpg")
        self.assertTrue(images[1].startswith("data:image/png;base64,"))

    def test_more_than_16_reference_images_is_rejected(self) -> None:
        with self.assertRaisesRegex(generate_image.ApiError, "最多支持 16 张"):
            generate_image.build_image_inputs(
                [f"https://example.com/{index}.png" for index in range(17)],
                None,
            )

    def test_result_parsing_and_filename_helpers_remain_compatible(self) -> None:
        task = {
            "result": {
                "images": [
                    {"url": "https://example.com/result_task_abc.png"},
                    {"url": ["https://example.com/second.webp"]},
                ]
            }
        }

        self.assertEqual(
            generate_image.collect_image_urls(task),
            [
                "https://example.com/result_task_abc.png",
                "https://example.com/second.webp",
            ],
        )
        self.assertEqual(
            generate_image.image_filename_stem(
                "https://example.com/result_task_abc.png",
                "fallback",
                1,
            ),
            "abc",
        )
        self.assertEqual(generate_image.task_id_filename_stem("task_abc"), "abc")
        self.assertEqual(
            generate_image.suffix_from_url("https://example.com/image.jpeg?x=1"),
            ".jpeg",
        )


if __name__ == "__main__":
    unittest.main()
