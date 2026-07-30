from __future__ import annotations

from app.domain.errors import (
    InvalidBoundingBoxError,
    LayoutOverflowError,
)
from app.domain.layout import LayoutRequest
from app.geometry.scale import (
    calculate_product_height_px,
    calculate_product_width_px,
)
from app.schemas.layout import LayoutPlan, ProductPlacement


LAYOUT_VERSION = "1.0"


def create_layout_plan(request: LayoutRequest) -> LayoutPlan:
    _validate_person_within_canvas(request)
    _validate_ground_line(request)

    product_height_px = calculate_product_height_px(
        person_height_px=request.person.height_px,
        person_height_cm=request.model_profile.height_cm,
        product_height_cm=request.product_profile.height_cm,
        perspective_factor=request.perspective_factor,
    )
    product_width_px = calculate_product_width_px(
        product_height_px=product_height_px,
        product_width_cm=request.product_profile.width_cm,
        product_height_cm=request.product_profile.height_cm,
    )

    if request.product_side == "right":
        product_x = request.person.right + request.gap_px
    else:
        product_x = request.person.x - request.gap_px - product_width_px
    product_y = request.ground_y - product_height_px

    _validate_product_within_canvas(
        request=request,
        x=product_x,
        y=product_y,
        width_px=product_width_px,
        height_px=product_height_px,
    )

    scale_ratio = (
        request.person.height_px
        / request.model_profile.height_cm
        * request.perspective_factor
    )
    product = ProductPlacement(
        x=product_x,
        y=product_y,
        width_px=product_width_px,
        height_px=product_height_px,
        bottom_y=request.ground_y,
        scale_ratio=scale_ratio,
        perspective_factor=request.perspective_factor,
    )
    warnings: list[str] = []
    if request.person.bottom != request.ground_y:
        warnings.append(
            f"人物 bbox 底部 {request.person.bottom} "
            f"与 ground_y {request.ground_y} 不一致"
        )

    return LayoutPlan(
        canvas=request.canvas,
        person=request.person,
        product=product,
        warnings=tuple(warnings),
        version=LAYOUT_VERSION,
    )


def format_layout_constraints(
    request: LayoutRequest,
    plan: LayoutPlan,
) -> str:
    product = request.product_profile
    side_text = "left" if request.product_side == "left" else "right"
    return "\n".join(
        (
            "LAYOUT CONSTRAINTS:",
            f"- Canvas: {plan.canvas.width_px} x {plan.canvas.height_px} px",
            (
                "- Person bounding box: "
                f"x={plan.person.x}, y={plan.person.y}, "
                f"width={plan.person.width_px}, "
                f"height={plan.person.height_px} px"
            ),
            f"- Model real height: {_format_number(request.model_profile.height_cm)} cm",
            (
                "- Product real size: "
                f"{_format_number(product.width_cm)} x "
                f"{_format_number(product.height_cm)} x "
                f"{_format_number(product.depth_cm)} cm"
            ),
            (
                "- Product target box: "
                f"x={plan.product.x}, y={plan.product.y}, "
                f"width={plan.product.width_px}, "
                f"height={plan.product.height_px} px"
            ),
            f"- Product bottom aligned to y={plan.product.bottom_y}",
            f"- Product placed on the {side_text} side",
            "- Keep the person and product on the same ground plane",
        )
    )


def _validate_person_within_canvas(request: LayoutRequest) -> None:
    person = request.person
    canvas = request.canvas
    if person.right > canvas.width_px or person.bottom > canvas.height_px:
        raise InvalidBoundingBoxError(
            "人物 bbox 超出画布: "
            f"bbox=(x={person.x}, y={person.y}, "
            f"width={person.width_px}, height={person.height_px}), "
            f"canvas={canvas.width_px}x{canvas.height_px}"
        )


def _validate_ground_line(request: LayoutRequest) -> None:
    if request.ground_y > request.canvas.height_px:
        raise InvalidBoundingBoxError(
            f"ground_y={request.ground_y} 超出画布高度 "
            f"{request.canvas.height_px}"
        )


def _validate_product_within_canvas(
    *,
    request: LayoutRequest,
    x: int,
    y: int,
    width_px: int,
    height_px: int,
) -> None:
    right = x + width_px
    bottom = y + height_px
    canvas = request.canvas
    if (
        x < 0
        or y < 0
        or right > canvas.width_px
        or bottom > canvas.height_px
    ):
        raise LayoutOverflowError(
            "商品布局超出画布: "
            f"side={request.product_side}, "
            f"bbox=(x={x}, y={y}, width={width_px}, height={height_px}), "
            f"canvas={canvas.width_px}x{canvas.height_px}"
        )


def _format_number(value: float) -> str:
    return f"{value:g}"
