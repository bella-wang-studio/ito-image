from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class GenerationStatus(str, Enum):
    SUBMITTED = "submitted"
    IN_PROGRESS = "in_progress"
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


RUNNING_STATUSES = frozenset(
    {
        GenerationStatus.SUBMITTED.value,
        GenerationStatus.IN_PROGRESS.value,
        GenerationStatus.PENDING.value,
        GenerationStatus.PROCESSING.value,
    }
)
FINAL_STATUSES = frozenset(
    {
        GenerationStatus.COMPLETED.value,
        GenerationStatus.FAILED.value,
        GenerationStatus.CANCELLED.value,
    }
)


@dataclass(frozen=True)
class GeneratedImage:
    url: str


@dataclass(frozen=True)
class GenerationJob:
    task_id: str
    status: str
    progress: int | float | None = None
    images: tuple[GeneratedImage, ...] = ()
    raw: Mapping[str, Any] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", self.status.lower())

    @property
    def is_running(self) -> bool:
        return self.status in RUNNING_STATUSES

    @property
    def is_terminal(self) -> bool:
        return self.status in FINAL_STATUSES

    @property
    def is_completed(self) -> bool:
        return self.status == GenerationStatus.COMPLETED.value

    @property
    def image_urls(self) -> list[str]:
        return [image.url for image in self.images]
