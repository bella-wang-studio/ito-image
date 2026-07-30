from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.domain.errors import (
    InvalidProfileError,
    ProfileFileNotFoundError,
    UnsupportedProfileFormatError,
)
from app.services.asset_loader import load_model_profile, load_product_profile


class AssetLoaderTests(unittest.TestCase):
    def test_json_profile_paths_are_relative_to_profile_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            profile_dir = Path(directory) / "product"
            profile_dir.mkdir()
            profile_path = profile_dir / "product.json"
            profile_path.write_text(
                json.dumps(
                    {
                        "sku": "SKU-1",
                        "name": "测试商品",
                        "category": "bag",
                        "width_cm": 35,
                        "height_cm": 55,
                        "depth_cm": 23,
                        "hero_image": "images/front.png",
                        "views": {
                            "front": "images/front.png",
                            "angle_45": "images/angle.png",
                        },
                        "include_wheels_in_height": True,
                        "include_handle_in_height": False,
                    }
                ),
                encoding="utf-8",
            )

            profile = load_product_profile(profile_path)

            self.assertEqual(
                profile.hero_image,
                (profile_dir / "images/front.png").resolve(),
            )
            self.assertEqual(
                profile.views["angle_45"],
                (profile_dir / "images/angle.png").resolve(),
            )

    def test_model_reference_paths_are_resolved(self) -> None:
        fixture = Path(__file__).parent / "fixtures/model.json"

        profile = load_model_profile(fixture)

        self.assertEqual(
            profile.reference_images,
            ((fixture.parent / "贝拉.jpg").resolve(),),
        )

    def test_missing_profile_has_specific_error(self) -> None:
        path = Path("/tmp/missing-product-profile.json")

        with self.assertRaisesRegex(ProfileFileNotFoundError, str(path)):
            load_product_profile(path)

    def test_unsupported_format_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "product.yaml"
            path.write_text("name: test", encoding="utf-8")

            with self.assertRaisesRegex(
                UnsupportedProfileFormatError,
                "仅支持 JSON",
            ):
                load_product_profile(path)

    def test_invalid_json_reports_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "product.json"
            path.write_text("{", encoding="utf-8")

            with self.assertRaisesRegex(InvalidProfileError, str(path)):
                load_product_profile(path)


if __name__ == "__main__":
    unittest.main()
