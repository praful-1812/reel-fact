"""Background job queue — processes fact-check jobs off the request thread.

Same shape as the `vectorless-rag` ingestion queue: a small async worker pool
pulls job ids off an asyncio.Queue and runs the pipeline. The HTTP handler returns
immediately after enqueuing, and the app polls for the result.
"""

import asyncio
import logging

from app.services.pipeline import run_factcheck

logger = logging.getLogger(__name__)


class FactCheckQueue:
    """Async queue that processes fact-check jobs with a bounded worker pool."""

    def __init__(self, max_concurrent: int = 2):
        self._queue: asyncio.Queue[int] = asyncio.Queue()
        self._max_concurrent = max_concurrent
        self._workers: list[asyncio.Task] = []
        self._processing: set[int] = set()

    async def start(self) -> None:
        for i in range(self._max_concurrent):
            self._workers.append(asyncio.create_task(self._worker(i)))
        logger.info(f"[Queue] Started {self._max_concurrent} fact-check worker(s)")

    async def stop(self) -> None:
        for _ in self._workers:
            await self._queue.put(-1)  # sentinel
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("[Queue] Stopped all workers")

    async def enqueue(self, job_id: int) -> None:
        await self._queue.put(job_id)
        logger.info(f"[Queue] Enqueued job_id={job_id} (queue size: {self._queue.qsize()})")

    @property
    def queue_size(self) -> int:
        return self._queue.qsize()

    async def _worker(self, worker_id: int) -> None:
        logger.info(f"[Queue] Worker {worker_id} ready")
        while True:
            job_id = await self._queue.get()
            if job_id == -1:  # sentinel → shut down
                break

            self._processing.add(job_id)
            try:
                logger.info(f"[Queue] Worker {worker_id} processing job_id={job_id}")
                await run_factcheck(job_id)
            except Exception:  # noqa: BLE001 — never let a worker die
                logger.exception(f"[Queue] Worker {worker_id} failed job_id={job_id}")
            finally:
                self._processing.discard(job_id)
                self._queue.task_done()


# Singleton instance used by the API + app startup.
factcheck_queue = FactCheckQueue(max_concurrent=2)
