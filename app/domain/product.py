from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from app.domain.errors import InvalidDimensionError, InvalidProfileError


@dataclass(frozen=True)
class ProductProfile:
    sku: str
    name: str
    category: str
    width_cm: float
    height_cm: float
    depth_cm: float
    hero_image: Path
    views: Mapping[str, Path]
    include_wheels_in_height: bool
    include_handle_in_height: bool

    def __post_init__(self) -> None:
        for field_name in ("sku", "name", "category"):
            if not getattr(self, field_name):
                raise InvalidProfileError(f"商品字段 {field_name} 不能为空")
        for field_name in ("width_cm", "height_cm", "depth_cm"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise InvalidDimensionError(
                    f"商品字段 {field_name} 必须是大于 0 的数字，实际为 {value!r}"
                )
        if not isinstance(self.hero_image, Path):
            raise InvalidProfileError("商品字段 hero_image 必须是路径")
        if not isinstance(self.views, Mapping):
            raise InvalidProfileError("商品字段 views 必须是对象")
        object.__setattr__(self, "views", MappingProxyType(dict(self.views)))
