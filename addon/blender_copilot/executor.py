"""Main-thread execution queue.

bpy is not thread-safe. The socket server runs on a worker thread and must never
touch bpy directly. Instead it pushes a Job here; a bpy.app.timers callback --
which Blender guarantees to run on the main thread -- drains the queue, executes
each job, and hands the result back through the job's Event.

This is the single most important invariant in the addon. Every bpy access in
this codebase happens inside `_drain`, downstream of the timer.
"""

import queue
import threading
import traceback

# Jobs submitted by socket threads, drained on the main thread.
_jobs: "queue.Queue[Job]" = queue.Queue()

# How often the main thread checks for work. 20ms keeps latency imperceptible
# while staying far cheaper than Blender's own event loop overhead.
TICK = 0.02


class Job:
    """A unit of work to run on Blender's main thread."""

    __slots__ = ("fn", "done", "result", "error")

    def __init__(self, fn):
        self.fn = fn
        self.done = threading.Event()
        self.result = None
        self.error = None

    def run(self):
        try:
            self.result = self.fn()
        except BaseException as exc:  # noqa: BLE001 - must never kill the timer
            self.error = {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            }
        finally:
            self.done.set()


def submit(fn, timeout=60.0):
    """Run `fn` on the main thread from a worker thread and wait for its result.

    Returns (result, error). `error` is None on success. A timeout is reported
    as an error rather than raising, so one wedged job can't take down the
    connection handler.
    """
    job = Job(fn)
    _jobs.put(job)
    if not job.done.wait(timeout):
        return None, {
            "type": "TimeoutError",
            "message": f"job did not complete within {timeout}s",
            "traceback": "",
        }
    return job.result, job.error


def _drain():
    """Timer callback. Runs on the main thread."""
    # Bound the batch so a flood of jobs can't stall the UI within one tick.
    for _ in range(16):
        try:
            job = _jobs.get_nowait()
        except queue.Empty:
            break
        job.run()
    return TICK


def start():
    if not bpy_timers_has(_drain):
        import bpy

        bpy.app.timers.register(_drain, persistent=True)


def stop():
    import bpy

    if bpy_timers_has(_drain):
        bpy.app.timers.unregister(_drain)
    # Release anyone still blocked so threads don't hang on shutdown.
    while True:
        try:
            job = _jobs.get_nowait()
        except queue.Empty:
            break
        job.error = {"type": "Shutdown", "message": "addon unregistered", "traceback": ""}
        job.done.set()


def bpy_timers_has(fn):
    import bpy

    return bpy.app.timers.is_registered(fn)
