from __future__ import annotations

import math

from app.domain.errors import InvalidDimensionError


def calculate_product_height_px(
    person_height_px: int | float,
    person_height_cm: int | float,
    product_height_cm: int | float,
    perspective_factor: int | float = 1.0,
) -> int:
    """按人物真实身高与像素高度计算商品目标像素高度。"""
    _validate_positive_number(person_height_px, "person_height_px")
    _validate_positive_number(person_height_cm, "person_height_cm")
    _validate_positive_number(product_height_cm, "product_height_cm")
    _validate_positive_number(perspective_factor, "perspective_factor")
    raw_height = (
        float(person_height_px)
        * float(product_height_cm)
        / float(person_height_cm)
        * float(perspective_factor)
    )
    return _round_half_up(raw_height)


def calculate_product_width_px(
    product_height_px: int | float,
    product_width_cm: int | float,
    product_height_cm: int | float,
) -> int:
    """按商品真实宽高比计算商品目标像素宽度。"""
    _validate_positive_number(product_height_px, "product_height_px")
    _validate_positive_number(product_width_cm, "product_width_cm")
    _validate_positive_number(product_height_cm, "product_height_cm")
    raw_width = (
        float(product_height_px)
        * float(product_width_cm)
        / float(product_height_cm)
    )
    return _round_half_up(raw_width)


def _round_half_up(value: float) -> int:
    return math.floor(value + 0.5)


def _validate_positive_number(value: object, field_name: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or value <= 0
    ):
        raise InvalidDimensionError(
            f"{field_name} 必须是大于 0 的数字，实际为 {value!r}"
        )
