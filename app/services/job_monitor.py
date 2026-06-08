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
        inspect = celery_app.control.inspect()

        workers = inspect.ping() or {}
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