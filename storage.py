from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

class BaseStorage(ABC):

    @abstractmethod
    async def get_data(self, key: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    async def set_data(self, key: str, data: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    async def get_state(self, key: str) -> Optional[str]:
        pass

    @abstractmethod
    async def set_state(self, key: str, state: Optional[str]) -> None:
        pass


class MemoryStorage(BaseStorage):

    def __init__(self):
        self._data: Dict[str, Dict[str, Any]] = {}
        self._states: Dict[str, Optional[str]] = {}

    async def get_data(self, key: str) -> Dict[str, Any]:
        return self._data.get(key, {}).copy()

    async def set_data(self, key: str, data: Dict[str, Any]) -> None:
        self._data[key] = data.copy()

    async def get_state(self, key: str) -> Optional[str]:
        return self._states.get(key)

    async def set_state(self, key: str, state: Optional[str]) -> None:
        if state is None:
            self._states.pop(key, None)
        else:
            self._states[key] = state

class JSONStorage(BaseStorage):

    def __init__(self, file_path: str = "bot_storage.json"):
        self.file_path = Path(file_path)
        self._lock = asyncio.Lock()
        self._data: Dict[str, Dict[str, Any]] = {}
        self._states: Dict[str, Optional[str]] = {}
        self._load()

    def _load(self):
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                self._data = saved.get("data", {})
                self._states = saved.get("states", {})
            except Exception as e:
                print(f"Error loading storage: {e}")
                self._data = {}
                self._states = {}
        else:
            self._data = {}
            self._states = {}

    def _save(self):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump({"data": self._data, "states": self._states}, f, ensure_ascii=False, indent=2)

    async def get_data(self, key: str) -> Dict[str, Any]:
        async with self._lock:
            return self._data.get(key, {}).copy()

    async def set_data(self, key: str, data: Dict[str, Any]) -> None:
        async with self._lock:
            self._data[key] = data.copy()
            self._save()

    async def get_state(self, key: str) -> Optional[str]:
        async with self._lock:
            return self._states.get(key)

    async def set_state(self, key: str, state: Optional[str]) -> None:
        async with self._lock:
            if state is None:
                self._states.pop(key, None)
            else:
                self._states[key] = state
            self._save()