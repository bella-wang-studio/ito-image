from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.domain.errors import (
    InvalidBoundingBoxError,
    InvalidDimensionError,
    InvalidProfileError,
)


@dataclass(frozen=True)
class CanvasSpec:
    width_px: int
    height_px: int

    def __post_init__(self) -> None:
        _validate_positive_int(self.width_px, "canvas.width_px")
        _validate_positive_int(self.height_px, "canvas.height_px")

    def to_dict(self) -> dict[str, int]:
        return {"width_px": self.width_px, "height_px": self.height_px}


@dataclass(frozen=True)
class PersonPlacement:
    x: int
    y: int
    width_px: int
    height_px: int

    def __post_init__(self) -> None:
        _validate_non_negative_int(self.x, "person.x")
        _validate_non_negative_int(self.y, "person.y")
        _validate_positive_int(self.width_px, "person.width_px")
        _validate_positive_int(self.height_px, "person.height_px")

    @property
    def right(self) -> int:
        return self.x + self.width_px

    @property
    def bottom(self) -> int:
        return self.y + self.height_px

    def to_dict(self) -> dict[str, int]:
        return {
            "x": self.x,
            "y": self.y,
            "width_px": self.width_px,
            "height_px": self.height_px,
        }


@dataclass(frozen=True)
class ProductPlacement:
    x: int
    y: int
    width_px: int
    height_px: int
    bottom_y: int
    scale_ratio: float
    perspective_factor: float

    def __post_init__(self) -> None:
        _validate_non_negative_int(self.x, "product.x")
        _validate_non_negative_int(self.y, "product.y")
        _validate_positive_int(self.width_px, "product.width_px")
        _validate_positive_int(self.height_px, "product.height_px")
        _validate_non_negative_int(self.bottom_y, "product.bottom_y")
        _validate_positive_number(self.scale_ratio, "product.scale_ratio")
        _validate_positive_number(
            self.perspective_factor,
            "product.perspective_factor",
        )
        if self.y + self.height_px != self.bottom_y:
            raise InvalidBoundingBoxError(
                "product.y + product.height_px 必须等于 product.bottom_y"
            )

    @property
    def right(self) -> int:
        return self.x + self.width_px

    def to_dict(self) -> dict[str, int | float]:
        return {
            "x": self.x,
            "y": self.y,
            "width_px": self.width_px,
            "height_px": self.height_px,
            "bottom_y": self.bottom_y,
            "scale_ratio": self.scale_ratio,
            "perspective_factor": self.perspective_factor,
        }


@dataclass(frozen=True)
class LayoutPlan:
    canvas: CanvasSpec
    person: PersonPlacement
    product: ProductPlacement
    warnings: tuple[str, ...] = ()
    version: str = "1.0"

    def __post_init__(self) -> None:
        if not self.version:
            raise InvalidProfileError("layout.version 不能为空")
        if not all(isinstance(warning, str) for warning in self.warnings):
            raise InvalidProfileError("layout.warnings 必须全部是字符串")

    def to_dict(self) -> dict[str, Any]:
        return {
            "canvas": self.canvas.to_dict(),
            "person": self.person.to_dict(),
            "product": self.product.to_dict(),
            "warnings": list(self.warnings),
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> LayoutPlan:
        try:
            canvas_data = data["canvas"]
            person_data = data["person"]
            product_data = data["product"]
            warnings = data.get("warnings", [])
            version = data["version"]
        except (KeyError, TypeError) as exc:
            raise InvalidProfileError(
                f"布局 JSON 缺少字段或结构错误: {exc}"
            ) from exc
        if not isinstance(canvas_data, Mapping):
            raise InvalidProfileError("布局字段 canvas 必须是对象")
        if not isinstance(person_data, Mapping):
            raise InvalidProfileError("布局字段 person 必须是对象")
        if not isinstance(product_data, Mapping):
            raise InvalidProfileError("布局字段 product 必须是对象")
        if (
            not isinstance(warnings, list)
            or not all(isinstance(item, str) for item in warnings)
        ):
            raise InvalidProfileError("布局字段 warnings 必须是字符串数组")
        if not isinstance(version, str):
            raise InvalidProfileError("布局字段 version 必须是字符串")
        try:
            return cls(
                canvas=CanvasSpec(
                    width_px=canvas_data["width_px"],
                    height_px=canvas_data["height_px"],
                ),
                person=PersonPlacement(
                    x=person_data["x"],
                    y=person_data["y"],
                    width_px=person_data["width_px"],
                    height_px=person_data["height_px"],
                ),
                product=ProductPlacement(
                    x=product_data["x"],
                    y=product_data["y"],
                    width_px=product_data["width_px"],
                    height_px=product_data["height_px"],
                    bottom_y=product_data["bottom_y"],
                    scale_ratio=product_data["scale_ratio"],
                    perspective_factor=product_data["perspective_factor"],
                ),
                warnings=tuple(warnings),
                version=version,
            )
        except KeyError as exc:
            raise InvalidProfileError(
                f"布局 JSON 缺少字段: {exc.args[0]}"
            ) from exc


def _validate_positive_int(value: object, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise InvalidDimensionError(
            f"{field_name} 必须是大于 0 的整数，实际为 {value!r}"
        )


def _validate_non_negative_int(value: object, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise InvalidBoundingBoxError(
            f"{field_name} 必须是大于等于 0 的整数，实际为 {value!r}"
        )


def _validate_positive_number(value: object, field_name: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or value <= 0
    ):
        raise InvalidDimensionError(
            f"{field_name} 必须是大于 0 的数字，实际为 {value!r}"
        )
