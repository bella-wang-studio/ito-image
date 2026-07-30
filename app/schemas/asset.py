from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from app.domain.errors import InvalidProfileError
from app.domain.model_profile import ModelProfile
from app.domain.product import ProductProfile


def parse_product_profile(
    data: Mapping[str, Any],
    *,
    base_dir: Path,
) -> ProductProfile:
    _require_mapping(data, "商品资料")
    return ProductProfile(
        sku=_require_string(data, "sku", "商品"),
        name=_require_string(data, "name", "商品"),
        category=_require_string(data, "category", "商品"),
        width_cm=_require_number(data, "width_cm", "商品"),
        height_cm=_require_number(data, "height_cm", "商品"),
        depth_cm=_require_number(data, "depth_cm", "商品"),
        hero_image=_resolve_relative_path(
            _require_string(data, "hero_image", "商品"),
            base_dir,
        ),
        views=_parse_views(data, base_dir),
        include_wheels_in_height=_require_bool(
            data,
            "include_wheels_in_height",
            "商品",
        ),
        include_handle_in_height=_require_bool(
            data,
            "include_handle_in_height",
            "商品",
        ),
    )


def parse_model_profile(
    data: Mapping[str, Any],
    *,
    base_dir: Path,
) -> ModelProfile:
    _require_mapping(data, "模特资料")
    raw_images = data.get("reference_images")
    if (
        not isinstance(raw_images, Sequence)
        or isinstance(raw_images, (str, bytes))
        or not raw_images
    ):
        raise InvalidProfileError(
            "模特字段 reference_images 必须是非空字符串数组"
        )
    reference_images: list[Path] = []
    for index, value in enumerate(raw_images):
        if not isinstance(value, str) or not value.strip():
            raise InvalidProfileError(
                "模特字段 reference_images"
                f"[{index}] 必须是非空字符串，实际为 {value!r}"
            )
        reference_images.append(_resolve_relative_path(value, base_dir))

    return ModelProfile(
        id=_require_string(data, "id", "模特"),
        name=_require_string(data, "name", "模特"),
        height_cm=_require_number(data, "height_cm", "模特"),
        reference_images=tuple(reference_images),
    )


def _parse_views(
    data: Mapping[str, Any],
    base_dir: Path,
) -> dict[str, Path]:
    raw_views = data.get("views")
    if not isinstance(raw_views, Mapping):
        raise InvalidProfileError(
            f"商品字段 views 必须是对象，实际为 {raw_views!r}"
        )
    views: dict[str, Path] = {}
    for name, value in raw_views.items():
        if not isinstance(name, str) or not name:
            raise InvalidProfileError(
                f"商品字段 views 的视角名必须是非空字符串，实际为 {name!r}"
            )
        if not isinstance(value, str) or not value.strip():
            raise InvalidProfileError(
                f"商品字段 views.{name} 必须是非空字符串，实际为 {value!r}"
            )
        views[name] = _resolve_relative_path(value, base_dir)
    return views


def _require_mapping(value: object, label: str) -> None:
    if not isinstance(value, Mapping):
        raise InvalidProfileError(
            f"{label}根节点必须是 JSON 对象，实际为 {type(value).__name__}"
        )


def _require_string(
    data: Mapping[str, Any],
    field_name: str,
    profile_name: str,
) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise InvalidProfileError(
            f"{profile_name}字段 {field_name} 必须是非空字符串，实际为 {value!r}"
        )
    return value.strip()


def _require_number(
    data: Mapping[str, Any],
    field_name: str,
    profile_name: str,
) -> float:
    value = data.get(field_name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidProfileError(
            f"{profile_name}字段 {field_name} 必须是数字，实际为 {value!r}"
        )
    return float(value)


def _require_bool(
    data: Mapping[str, Any],
    field_name: str,
    profile_name: str,
) -> bool:
    value = data.get(field_name)
    if not isinstance(value, bool):
        raise InvalidProfileError(
            f"{profile_name}字段 {field_name} 必须是布尔值，实际为 {value!r}"
        )
    return value


def _resolve_relative_path(value: str, base_dir: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()
