from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.domain.errors import (
    InvalidBoundingBoxError,
    InvalidDimensionError,
)
from app.domain.model_profile import ModelProfile
from app.domain.product import ProductProfile
from app.schemas.layout import CanvasSpec, PersonPlacement


ProductSide = Literal["left", "right"]


@dataclass(frozen=True)
class LayoutRequest:
    canvas: CanvasSpec
    person: PersonPlacement
    model_profile: ModelProfile
    product_profile: ProductProfile
    product_side: ProductSide
    ground_y: int
    perspective_factor: float = 1.0
    gap_px: int = 50

    def __post_init__(self) -> None:
        if self.product_side not in {"left", "right"}:
            raise InvalidBoundingBoxError(
                "product_side 必须是 left 或 right，"
                f"实际为 {self.product_side!r}"
            )
        if isinstance(self.ground_y, bool) or not isinstance(self.ground_y, int):
            raise InvalidBoundingBoxError(
                f"ground_y 必须是整数，实际为 {self.ground_y!r}"
            )
        if self.ground_y < 0:
            raise InvalidBoundingBoxError(
                f"ground_y 不能小于 0，实际为 {self.ground_y}"
            )
        if (
            isinstance(self.perspective_factor, bool)
            or not isinstance(self.perspective_factor, (int, float))
            or self.perspective_factor <= 0
        ):
            raise InvalidDimensionError(
                "perspective_factor 必须大于 0，"
                f"实际为 {self.perspective_factor!r}"
            )
        if isinstance(self.gap_px, bool) or not isinstance(self.gap_px, int):
            raise InvalidDimensionError(
                f"gap_px 必须是整数，实际为 {self.gap_px!r}"
            )
        if self.gap_px < 0:
            raise InvalidDimensionError(
                f"gap_px 不能小于 0，实际为 {self.gap_px}"
            )
