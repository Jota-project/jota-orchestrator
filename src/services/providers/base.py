# src/services/providers/base.py
from abc import ABC, abstractmethod
from typing import AsyncGenerator

from .types import InferRequest, InferEvent, ProviderCapabilities


class BaseProvider(ABC):
    """
    Common interface for all inference adapters.

    Each adapter must:
    - Declare its capabilities via the `capabilities` property.
    - Implement `infer()` yielding InferEvent instances.
    - Always yield DoneEvent as the final event.
    - Yield ErrorEvent for recoverable stream errors; raise for unrecoverable ones.
    """

    @property
    @abstractmethod
    def capabilities(self) -> ProviderCapabilities: ...

    @abstractmethod
    async def infer(
        self, request: InferRequest
    ) -> AsyncGenerator[InferEvent, None]: ...

    @abstractmethod
    async def list_models(self) -> list[str]: ...

    @abstractmethod
    async def check_health(self) -> bool: ...
