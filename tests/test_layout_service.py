from __future__ import annotations

import json
import unittest
from pathlib import Path

from app.domain.errors import (
    InvalidBoundingBoxError,
    LayoutOverflowError,
)
from app.domain.layout import LayoutRequest
from app.domain.model_profile import ModelProfile
from app.domain.product import ProductProfile
from app.schemas.layout import CanvasSpec, LayoutPlan, PersonPlacement
from app.services.layout_service import (
    create_layout_plan,
    format_layout_constraints,
)


def make_product() -> ProductProfile:
    return ProductProfile(
        sku="PISTACHIO-2-20",
        name="PISTACHIO 2 STRIPED TRUNK 20 Inch",
        category="hard_luggage",
        width_cm=35,
        height_cm=55,
        depth_cm=23,
        hero_image=Path("/profiles/front.png"),
        views={"front": Path("/profiles/front.png")},
        include_wheels_in_height=True,
        include_handle_in_height=False,
    )


def make_model() -> ModelProfile:
    return ModelProfile(
        id="bella",
        name="贝拉",
        height_cm=170,
        reference_images=(Path("/profiles/贝拉.jpg"),),
    )


def make_request(
    *,
    person: PersonPlacement,
    side: str,
    ground_y: int = 1430,
) -> LayoutRequest:
    return LayoutRequest(
        canvas=CanvasSpec(1024, 1536),
        person=person,
        model_profile=make_model(),
        product_profile=make_product(),
        product_side=side,
        ground_y=ground_y,
    )


class LayoutServiceTests(unittest.TestCase):
    def test_places_product_on_right(self) -> None:
        request = make_request(
            person=PersonPlacement(130, 180, 500, 1260),
            side="right",
        )

        plan = create_layout_plan(request)

        self.assertEqual(plan.product.x, 680)
        self.assertEqual(plan.product.y, 1022)
        self.assertEqual(plan.product.width_px, 260)
        self.assertEqual(plan.product.height_px, 408)
        self.assertEqual(plan.product.bottom_y, 1430)
        self.assertEqual(
            plan.warnings,
            ("人物 bbox 底部 1440 与 ground_y 1430 不一致",),
        )

    def test_places_product_on_left(self) -> None:
        request = make_request(
            person=PersonPlacement(400, 170, 500, 1260),
            side="left",
        )

        plan = create_layout_plan(request)

        self.assertEqual(plan.product.x, 90)
        self.assertEqual(plan.product.right, 350)
        self.assertEqual(plan.product.bottom_y, 1430)

    def test_product_overflow_is_explicit(self) -> None:
        request = make_request(
            person=PersonPlacement(300, 170, 500, 1260),
            side="right",
        )

        with self.assertRaisesRegex(LayoutOverflowError, "超出画布"):
            create_layout_plan(request)

    def test_person_bbox_outside_canvas_is_rejected(self) -> None:
        request = make_request(
            person=PersonPlacement(700, 170, 500, 1260),
            side="left",
        )

        with self.assertRaisesRegex(InvalidBoundingBoxError, "人物 bbox"):
            create_layout_plan(request)

    def test_layout_json_round_trip(self) -> None:
        request = make_request(
            person=PersonPlacement(130, 180, 500, 1260),
            side="right",
        )
        plan = create_layout_plan(request)

        restored = LayoutPlan.from_dict(json.loads(json.dumps(plan.to_dict())))

        self.assertEqual(restored, plan)

    def test_prompt_constraints_are_structured(self) -> None:
        request = make_request(
            person=PersonPlacement(130, 180, 500, 1260),
            side="right",
        )
        plan = create_layout_plan(request)

        constraints = format_layout_constraints(request, plan)

        self.assertIn("LAYOUT CONSTRAINTS:", constraints)
        self.assertIn("Product target box: x=680, y=1022", constraints)
        self.assertIn("Product placed on the right side", constraints)


if __name__ == "__main__":
    unittest.main()
