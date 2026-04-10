from abc import ABC, abstractmethod
from typing import AsyncGenerator


class BaseProvider(ABC):
    """
    Interfaz común para todos los adapters de inferencia.
    Cada yield del generador es un str (token de texto) o un dict
    con {"type": "tool_call", "payload": {...}}.
    """

    @abstractmethod
    async def infer(
        self,
        messages: list[dict],
        model: str,
        params: dict | None = None,
    ) -> AsyncGenerator[str | dict, None]:
        ...

    @abstractmethod
    async def list_models(self) -> list[str]:
        ...

    @abstractmethod
    async def check_health(self) -> bool:
        ...