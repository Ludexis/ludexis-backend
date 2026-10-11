from app.tasks.celery_app import celery_app


class JobMonitorService:
    def workers(self) -> dict:
        inspect = celery_app.control.inspect()
        return inspect.ping() or {}

    def active(self) -> dict:
        inspect = celery_app.control.inspect()
        return inspect.active() or {}

    def reserved(self) -> dict:
        inspect = celery_app.control.inspect()
        return inspect.reserved() or {}

    def stats(self) -> dict:
        # A broadcast waits its whole timeout for workers it doesn't know of; once ping has
        # counted them, the next two return as soon as each has answered.
        workers = celery_app.control.inspect().ping() or {}
        if not workers:
            return {"workers": 0, "active_tasks": 0, "reserved_tasks": 0}
        inspect = celery_app.control.inspect(destination=list(workers), limit=len(workers))
        active = inspect.active() or {}
        reserved = inspect.reserved() or {}

        return {
            "workers": len(workers),
            "active_tasks": sum(
                len(tasks)
                for tasks in active.values()
            ),
            "reserved_tasks": sum(
                len(tasks)
                for tasks in reserved.values()
            ),
        }
