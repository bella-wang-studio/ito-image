from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from app.domain.generation_job import GenerationJob
from app.schemas.job import GenerationRequest, PollingConfig


class ProviderError(RuntimeError):
    """图片生成 Provider 的统一异常。"""


class ProviderHTTPError(ProviderError):
    """Provider HTTP 请求失败。"""


class ProviderResponseError(ProviderError):
    """Provider 返回了无法使用的数据。"""


JobUpdateCallback = Callable[[GenerationJob], None]


class ImageGenerationProvider(ABC):
    @abstractmethod
    def submit(self, request: GenerationRequest) -> str:
        """提交生成任务并返回任务 ID。"""

    @abstractmethod
    def get_job(self, task_id: str) -> GenerationJob:
        """查询生成任务。"""

    @abstractmethod
    def wait_for_completion(
        self,
        task_id: str,
        polling: PollingConfig,
        on_update: JobUpdateCallback | None = None,
    ) -> GenerationJob:
        """轮询任务直至成功或失败。"""
