from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.schemas.layout import LayoutPlan
from src import generate_image


FIXTURES = Path(__file__).parent / "fixtures"
PRODUCT_PROFILE = FIXTURES / "product.json"
MODEL_PROFILE = FIXTURES / "model.json"


def layout_arguments(*, include_prompt: bool = False) -> list[str]:
    arguments = ["image"]
    if include_prompt:
        arguments.append("生成商品广告图")
    arguments.extend(
        (
            "--product-profile",
            str(PRODUCT_PROFILE),
            "--model-profile",
            str(MODEL_PROFILE),
            "--person-bbox",
            "130",
            "180",
            "500",
            "1260",
            "--canvas-size",
            "1024",
            "1536",
            "--product-side",
            "right",
            "--ground-y",
            "1430",
        )
    )
    return arguments


class LayoutCliTests(unittest.TestCase):
    def test_layout_only_does_not_call_provider(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        argv = layout_arguments() + ["--layout-only"]

        with (
            patch.object(sys, "argv", argv),
            patch.object(generate_image, "load_dotenv"),
            patch.object(generate_image, "submit_task") as submit_task,
            patch("sys.stdout", stdout),
            patch("sys.stderr", stderr),
            patch.dict(os.environ, {}, clear=True),
        ):
            result = generate_image.main()

        self.assertEqual(result, 0)
        submit_task.assert_not_called()
        self.assertEqual(stderr.getvalue(), "")
        plan = LayoutPlan.from_dict(json.loads(stdout.getvalue()))
        self.assertEqual(plan.product.height_px, 408)

    def test_layout_output_is_saved_and_readable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "nested/layout.json"
            argv = layout_arguments() + [
                "--layout-only",
                "--layout-output",
                str(output_path),
            ]
            with (
                patch.object(sys, "argv", argv),
                patch.object(generate_image, "load_dotenv"),
                patch("sys.stdout", io.StringIO()),
            ):
                result = generate_image.main()

            plan = LayoutPlan.from_dict(
                json.loads(output_path.read_text(encoding="utf-8"))
            )

        self.assertEqual(result, 0)
        self.assertEqual(plan.product.x, 680)

    def test_existing_cli_path_keeps_prompt_unchanged(self) -> None:
        with (
            patch.object(sys, "argv", ["image", "原始提示词"]),
            patch.object(generate_image, "load_dotenv"),
            patch.object(
                generate_image,
                "submit_task",
                return_value="task_1",
            ) as submit_task,
            patch.object(generate_image, "poll_task", return_value={}),
            patch.object(
                generate_image,
                "collect_image_urls",
                return_value=["https://example.com/image.png"],
            ),
            patch.object(
                generate_image,
                "download_images",
                return_value=[Path("output/image.png")],
            ),
            patch("sys.stdout", io.StringIO()),
            patch.dict(
                os.environ,
                {
                    "IMAGE_API_KEY": "secret",
                    "IMAGE_BASE_URL": "https://example.com",
                    "IMAGE_MODEL": "model",
                },
                clear=True,
            ),
        ):
            result = generate_image.main()

        self.assertEqual(result, 0)
        submitted_args = submit_task.call_args.args[0]
        self.assertEqual(submitted_args.prompt, "原始提示词")

    def test_generation_mode_appends_layout_constraints(self) -> None:
        argv = layout_arguments(include_prompt=True)
        with (
            patch.object(sys, "argv", argv),
            patch.object(generate_image, "load_dotenv"),
            patch.object(
                generate_image,
                "submit_task",
                return_value="task_1",
            ) as submit_task,
            patch.object(generate_image, "poll_task", return_value={}),
            patch.object(
                generate_image,
                "collect_image_urls",
                return_value=["https://example.com/image.png"],
            ),
            patch.object(
                generate_image,
                "download_images",
                return_value=[Path("output/image.png")],
            ),
            patch("sys.stdout", io.StringIO()),
            patch.dict(
                os.environ,
                {
                    "IMAGE_API_KEY": "secret",
                    "IMAGE_BASE_URL": "https://example.com",
                    "IMAGE_MODEL": "model",
                },
                clear=True,
            ),
        ):
            result = generate_image.main()

        self.assertEqual(result, 0)
        submitted_prompt = submit_task.call_args.args[0].prompt
        self.assertTrue(submitted_prompt.startswith("生成商品广告图\n\n"))
        self.assertIn("LAYOUT CONSTRAINTS:", submitted_prompt)
        self.assertIn("Product target box: x=680, y=1022", submitted_prompt)

    def test_incomplete_layout_arguments_are_rejected(self) -> None:
        stderr = io.StringIO()
        with (
            patch.object(
                sys,
                "argv",
                ["image", "--layout-only", "--ground-y", "100"],
            ),
            patch.object(generate_image, "load_dotenv"),
            patch("sys.stderr", stderr),
        ):
            result = generate_image.main()

        self.assertEqual(result, 2)
        self.assertIn("--product-profile", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
