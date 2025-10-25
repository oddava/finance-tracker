import time
from contextlib import asynccontextmanager

from loguru import logger


@asynccontextmanager
async def measure(label: str):
    """
    Async context manager to measure performance of a code block.
    Example:
        async with measure("get_user"):
            await db.get_user()
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = (time.perf_counter() - start) * 1000  # ms
        logger.info(f"[PERF] {label} took {duration:.2f} ms")
