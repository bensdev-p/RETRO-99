import threading

from retro99.tasks import Worker


def test_results_and_progress_are_delivered_on_poll():
    worker = Worker()
    events = []
    ui_thread = threading.get_ident()

    def job(report, n):
        for i in range(n):
            report(i)
        return n * 2

    def on_done(v):
        events.append(("done", v, threading.get_ident() == ui_thread))

    worker.submit(job, 3, on_progress=lambda p: events.append(("p", p)), on_done=on_done)
    worker.wait()
    assert events == [("p", 0), ("p", 1), ("p", 2), ("done", 6, True)]
    assert not worker.busy
    worker.shutdown()


def test_errors_are_reported():
    worker = Worker()
    errors = []

    def boom(report):
        raise RuntimeError("nope")

    worker.submit(boom, on_error=errors.append)
    worker.wait()
    assert isinstance(errors[0], RuntimeError)
    worker.shutdown()
