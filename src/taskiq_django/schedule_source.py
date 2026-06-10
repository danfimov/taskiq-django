from datetime import timedelta

from taskiq import ScheduleSource
from taskiq.scheduler.scheduled_task import ScheduledTask

from taskiq_django.models import TaskiqTaskSchedule


def _to_scheduled_task(row: TaskiqTaskSchedule) -> ScheduledTask:
    return ScheduledTask(
        schedule_id=row.schedule_id,
        task_name=row.task_name,
        labels=row.labels or {},
        args=row.args or [],
        kwargs=row.kwargs or {},
        cron=row.cron,
        cron_offset=row.cron_offset,
        time=row.time,
        interval=row.interval,
    )


class DjangoScheduleSource(ScheduleSource):
    """ScheduleSource backed by the Django ORM (TaskiqTaskSchedule model)."""

    async def get_schedules(self) -> list[ScheduledTask]:
        return [_to_scheduled_task(row) async for row in TaskiqTaskSchedule.objects.all()]

    async def add_schedule(self, schedule: ScheduledTask) -> None:
        interval = schedule.interval
        if isinstance(interval, timedelta):
            interval = int(interval.total_seconds())

        cron_offset = schedule.cron_offset
        if isinstance(cron_offset, timedelta):
            cron_offset = str(int(cron_offset.total_seconds()))

        await TaskiqTaskSchedule.objects.aupdate_or_create(
            schedule_id=schedule.schedule_id,
            defaults={
                "task_name": schedule.task_name,
                "labels": schedule.labels,
                "args": schedule.args,
                "kwargs": schedule.kwargs,
                "cron": schedule.cron,
                "cron_offset": cron_offset,
                "time": schedule.time,
                "interval": interval,
            },
        )

    async def delete_schedule(self, schedule_id: str) -> None:
        await TaskiqTaskSchedule.objects.filter(schedule_id=schedule_id).adelete()

    async def post_send(self, task: ScheduledTask) -> None:
        if task.time is not None:
            await self.delete_schedule(task.schedule_id)
