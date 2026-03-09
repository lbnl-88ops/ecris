import asyncio
import functools
from typing import Any, Callable


def with_lock_named(lock_name: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self: Any, *args, **kwargs) -> Any:
            try:
                lock = getattr(self, lock_name)
            except AttributeError:
                raise AttributeError(f"No lock named '{lock_name}' found")

            if not isinstance(lock, asyncio.Lock):
                raise TypeError(
                    f"'{lock_name}' must be an asyncio.Lock, not {{type(lock).__name__}}"
                )
            async with lock:
                return await func(self, *args, **kwargs)

        return wrapper

    return decorator
