__all__ = ["DjangoScheduleSource"]


def __getattr__(name: str):
    if name == "DjangoScheduleSource":
        from taskiq_django.schedule_source import DjangoScheduleSource

        return DjangoScheduleSource
    raise AttributeError(f"module 'taskiq_django' has no attribute {name!r}")
