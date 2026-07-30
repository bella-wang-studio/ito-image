from __future__ import annotations

import json
import unittest
from pathlib import Path

from app.domain.errors import InvalidDimensionError, InvalidProfileError
from app.schemas.asset import parse_model_profile, parse_product_profile


class AssetSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base_dir = Path("/tmp/profiles")
        self.product_data = {
            "sku": "SKU-1",
            "name": "测试商品",
            "category": "bag",
            "width_cm": 35,
            "height_cm": 55,
            "depth_cm": 23,
            "hero_image": "images/front.png",
            "views": {"front": "images/front.png"},
            "include_wheels_in_height": True,
            "include_handle_in_height": False,
        }

    def test_product_schema_builds_profile(self) -> None:
        profile = parse_product_profile(
            self.product_data,
            base_dir=self.base_dir,
        )

        self.assertEqual(profile.sku, "SKU-1")
        self.assertEqual(profile.height_cm, 55)
        self.assertEqual(
            profile.hero_image,
            (self.base_dir / "images/front.png").resolve(),
        )

    def test_product_dimensions_must_be_positive(self) -> None:
        data = dict(self.product_data, height_cm=0)

        with self.assertRaisesRegex(InvalidDimensionError, "height_cm"):
            parse_product_profile(data, base_dir=self.base_dir)

    def test_model_schema_requires_reference_images(self) -> None:
        with self.assertRaisesRegex(InvalidProfileError, "reference_images"):
            parse_model_profile(
                {
                    "id": "bella",
                    "name": "贝拉",
                    "height_cm": 170,
                    "reference_images": [],
                },
                base_dir=self.base_dir,
            )

    def test_schema_data_can_be_json_encoded(self) -> None:
        profile = parse_product_profile(
            self.product_data,
            base_dir=self.base_dir,
        )

        encoded = json.dumps(
            {
                "sku": profile.sku,
                "hero_image": str(profile.hero_image),
            }
        )

        self.assertIn("SKU-1", encoded)


if __name__ == "__main__":
    unittest.main()
