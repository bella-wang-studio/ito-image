from __future__ import annotations

from dataclasses import dataclass


SUPPORTED_RESOLUTIONS = frozenset({"1k", "2k", "4k"})
MAX_REFERENCE_IMAGES = 16


@dataclass(frozen=True)
class ProviderConfig:
    base_url: str
    api_key: str
    model: str

    def __post_init__(self) -> None:
        if not self.base_url:
            raise ValueError("base_url 不能为空")
        if not self.api_key:
            raise ValueError("api_key 不能为空")
        if not self.model:
            raise ValueError("model 不能为空")


@dataclass(frozen=True)
class PollingConfig:
    initial_delay: float = 10
    poll_interval: float = 5
    timeout: float = 180

    def __post_init__(self) -> None:
        if self.initial_delay < 0:
            raise ValueError("initial_delay 不能小于 0")
        if self.poll_interval < 0:
            raise ValueError("poll_interval 不能小于 0")
        if self.timeout < 0:
            raise ValueError("timeout 不能小于 0")


@dataclass(frozen=True)
class GenerationRequest:
    prompt: str
    size: str = "3:4"
    resolution: str = "1k"
    n: int = 1
    image_urls: tuple[str, ...] = ()
    official_fallback: bool = False

    def __post_init__(self) -> None:
        if not self.prompt:
            raise ValueError("prompt 不能为空")
        if self.resolution not in SUPPORTED_RESOLUTIONS:
            raise ValueError(f"不支持的分辨率: {self.resolution}")
        if self.n != 1:
            raise ValueError("当前接口固定生成 1 张图片")
        if len(self.image_urls) > MAX_REFERENCE_IMAGES:
            raise ValueError(f"参考图最多支持 {MAX_REFERENCE_IMAGES} 张")
