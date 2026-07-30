from __future__ import annotations

import unittest

from app.domain.errors import InvalidDimensionError
from app.geometry.scale import (
    calculate_product_height_px,
    calculate_product_width_px,
)


class ScaleTests(unittest.TestCase):
    def test_calculates_product_height_from_real_scale(self) -> None:
        result = calculate_product_height_px(
            person_height_px=1260,
            person_height_cm=170,
            product_height_cm=55,
        )

        self.assertEqual(result, 408)

    def test_perspective_factor_changes_height(self) -> None:
        normal = calculate_product_height_px(1260, 170, 55)
        reduced = calculate_product_height_px(
            1260,
            170,
            55,
            perspective_factor=0.5,
        )

        self.assertEqual(normal, 408)
        self.assertEqual(reduced, 204)

    def test_invalid_dimensions_and_factor_are_rejected(self) -> None:
        invalid_cases = (
            (0, 170, 55, 1.0, "person_height_px"),
            (1260, 0, 55, 1.0, "person_height_cm"),
            (1260, 170, -1, 1.0, "product_height_cm"),
            (1260, 170, 55, 0, "perspective_factor"),
        )
        for person_px, person_cm, product_cm, factor, field_name in invalid_cases:
            with self.subTest(field_name=field_name):
                with self.assertRaisesRegex(InvalidDimensionError, field_name):
                    calculate_product_height_px(
                        person_px,
                        person_cm,
                        product_cm,
                        factor,
                    )

    def test_product_width_uses_real_aspect_ratio(self) -> None:
        self.assertEqual(
            calculate_product_width_px(
                product_height_px=408,
                product_width_cm=35,
                product_height_cm=55,
            ),
            260,
        )


if __name__ == "__main__":
    unittest.main()
