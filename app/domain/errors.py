from __future__ import annotations


class ProfileFileNotFoundError(FileNotFoundError):
    """结构化资料文件不存在。"""


class InvalidProfileError(ValueError):
    """结构化资料内容无效。"""


class InvalidDimensionError(ValueError):
    """真实尺寸、像素尺寸或比例因子无效。"""


class InvalidBoundingBoxError(ValueError):
    """人物或商品边界框无效。"""


class LayoutOverflowError(ValueError):
    """布局元素超出画布。"""


class UnsupportedProfileFormatError(ValueError):
    """结构化资料文件格式不受支持。"""
