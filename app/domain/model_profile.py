from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.domain.errors import InvalidDimensionError, InvalidProfileError


@dataclass(frozen=True)
class ModelProfile:
    id: str
    name: str
    height_cm: float
    reference_images: tuple[Path, ...]

    def __post_init__(self) -> None:
        for field_name in ("id", "name"):
            if not getattr(self, field_name):
                raise InvalidProfileError(f"模特字段 {field_name} 不能为空")
        if (
            isinstance(self.height_cm, bool)
            or not isinstance(self.height_cm, (int, float))
            or self.height_cm <= 0
        ):
            raise InvalidDimensionError(
                "模特字段 height_cm 必须是大于 0 的数字，"
                f"实际为 {self.height_cm!r}"
            )
        if not self.reference_images:
            raise InvalidProfileError("模特字段 reference_images 不能为空")
        if not all(isinstance(path, Path) for path in self.reference_images):
            raise InvalidProfileError("模特字段 reference_images 必须全部是路径")
