from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.domain.errors import (
    InvalidProfileError,
    ProfileFileNotFoundError,
    UnsupportedProfileFormatError,
)
from app.domain.model_profile import ModelProfile
from app.domain.product import ProductProfile
from app.schemas.asset import parse_model_profile, parse_product_profile


def load_product_profile(path: Path | str) -> ProductProfile:
    profile_path, data = _load_json_object(path)
    return parse_product_profile(data, base_dir=profile_path.parent)


def load_model_profile(path: Path | str) -> ModelProfile:
    profile_path, data = _load_json_object(path)
    return parse_model_profile(data, base_dir=profile_path.parent)


def _load_json_object(path: Path | str) -> tuple[Path, Mapping[str, Any]]:
    profile_path = Path(path)
    if not profile_path.exists():
        raise ProfileFileNotFoundError(f"资料文件不存在: {profile_path}")
    if not profile_path.is_file():
        raise InvalidProfileError(f"资料路径不是文件: {profile_path}")
    if profile_path.suffix.lower() != ".json":
        raise UnsupportedProfileFormatError(
            f"不支持的资料格式 {profile_path.suffix or '<无扩展名>'}: "
            f"{profile_path}；第一版仅支持 JSON"
        )
    try:
        data = json.loads(profile_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise InvalidProfileError(
            f"资料文件不是合法 JSON: {profile_path}: "
            f"第 {exc.lineno} 行第 {exc.colno} 列"
        ) from exc
    if not isinstance(data, Mapping):
        raise InvalidProfileError(
            f"资料文件根节点必须是 JSON 对象: {profile_path}"
        )
    return profile_path.resolve(), data
