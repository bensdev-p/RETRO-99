"""Background jobs. The UI thread submits work and calls ``poll()`` once per frame;
progress and completion callbacks always run on the UI thread, inside ``poll()``.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)

Report = Callable[[Any], None]


@dataclass
class Job:
    fn: Callable[..., Any]
    args: tuple[Any, ...]
    on_done: Callable[[Any], None] | None = None
    on_error: Callable[[BaseException], None] | None = None
    on_progress: Callable[[Any], None] | None = None
    name: str = ""
    done: threading.Event = field(default_factory=threading.Event)


_STOP = object()


class Worker:
    """A small thread pool. Job functions receive a ``report(progress)`` callable first."""

    def __init__(self, threads: int = 2) -> None:
        self._jobs: queue.Queue[Any] = queue.Queue()
        self._events: queue.Queue[tuple[str, Job, Any]] = queue.Queue()
        self._pending = 0
        self._lock = threading.Lock()
        self._threads = [
            threading.Thread(target=self._run, name=f"retro99-worker-{i}", daemon=True)
            for i in range(threads)
        ]
        for t in self._threads:
            t.start()

    def submit(
        self,
        fn: Callable[..., Any],
        *args: Any,
        on_done: Callable[[Any], None] | None = None,
        on_error: Callable[[BaseException], None] | None = None,
        on_progress: Callable[[Any], None] | None = None,
        name: str = "",
    ) -> Job:
        job = Job(fn, args, on_done, on_error, on_progress, name or getattr(fn, "__name__", ""))
        with self._lock:
            self._pending += 1
        self._jobs.put(job)
        return job

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._pending > 0

    def _run(self) -> None:
        while True:
            job = self._jobs.get()
            if job is _STOP:
                return
            try:
                result = job.fn(lambda p, job=job: self._events.put(("progress", job, p)),
                                *job.args)  # fmt: skip
                self._events.put(("done", job, result))
            except BaseException as e:  # reported on the UI thread
                log.exception("job %s failed", job.name)
                self._events.put(("error", job, e))
            finally:
                job.done.set()

    def poll(self) -> None:
        """Deliver queued progress/results. Call from the UI thread."""
        while True:
            try:
                kind, job, payload = self._events.get_nowait()
            except queue.Empty:
                return
            if kind == "progress":
                if job.on_progress:
                    job.on_progress(payload)
                continue
            with self._lock:
                self._pending -= 1
            if kind == "done" and job.on_done:
                job.on_done(payload)
            elif kind == "error" and job.on_error:
                job.on_error(payload)

    def wait(self, timeout: float = 10.0) -> None:
        """Block until every submitted job has finished, then deliver results (tests/shutdown)."""
        deadline = time.monotonic() + timeout
        while self.busy and time.monotonic() < deadline:
            self.poll()
            time.sleep(0.005)
        self.poll()

    def shutdown(self) -> None:
        for _ in self._threads:
            self._jobs.put(_STOP)
