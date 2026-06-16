from datetime import datetime, timedelta, timezone

import pytest
from dirty_equals import IsPartialDict
from django.forms.models import model_to_dict
from taskiq.scheduler.scheduled_task import ScheduledTask

from taskiq_django.models import TaskiqTaskSchedule
from taskiq_django.schedule_source import DjangoScheduleSource


@pytest.fixture
def source() -> DjangoScheduleSource:
    return DjangoScheduleSource()


def make_task(**overrides) -> ScheduledTask:
    defaults = dict(
        schedule_id="sched-1",
        task_name="app:my_task",
        labels={"queue": "default"},
        args=[1, "two"],
        kwargs={"key": "value"},
        cron="0 * * * *",
    )
    defaults.update(overrides)
    return ScheduledTask(**defaults)


@pytest.mark.django_db(transaction=True)
class TestAddSchedule:
    async def test_creates_new_row(self, source: DjangoScheduleSource):
        await source.add_schedule(make_task())

        row = await TaskiqTaskSchedule.objects.aget(schedule_id="sched-1")
        assert model_to_dict(row) == IsPartialDict(
            task_name="app:my_task",
            labels={"queue": "default"},
            args=[1, "two"],
            kwargs={"key": "value"},
            cron="0 * * * *",
        )
        assert await TaskiqTaskSchedule.objects.account() == 1

    async def test_updates_existing_row(self, source: DjangoScheduleSource):
        await source.add_schedule(make_task())
        await source.add_schedule(make_task(task_name="app:renamed", cron="*/5 * * * *"))

        assert await TaskiqTaskSchedule.objects.account() == 1
        row = await TaskiqTaskSchedule.objects.aget(schedule_id="sched-1")
        assert row.task_name == "app:renamed"
        assert row.cron == "*/5 * * * *"

    async def test_interval_timedelta_stored_as_seconds(self, source: DjangoScheduleSource):
        await source.add_schedule(make_task(cron=None, interval=timedelta(minutes=2)))

        row = await TaskiqTaskSchedule.objects.aget(schedule_id="sched-1")
        assert row.interval == 120

    async def test_interval_int_stored_as_is(self, source: DjangoScheduleSource):
        await source.add_schedule(make_task(cron=None, interval=90))

        row = await TaskiqTaskSchedule.objects.aget(schedule_id="sched-1")
        assert row.interval == 90

    async def test_cron_offset_timedelta_stored_as_seconds_string(self, source: DjangoScheduleSource):
        await source.add_schedule(make_task(cron_offset=timedelta(hours=1)))

        row = await TaskiqTaskSchedule.objects.aget(schedule_id="sched-1")
        assert row.cron_offset == "3600"

    async def test_cron_offset_string_stored_as_is(self, source: DjangoScheduleSource):
        await source.add_schedule(make_task(cron_offset="Europe/Moscow"))

        row = await TaskiqTaskSchedule.objects.aget(schedule_id="sched-1")
        assert row.cron_offset == "Europe/Moscow"


@pytest.mark.django_db(transaction=True)
class TestGetSchedules:
    async def test_empty_returns_empty_list(self, source: DjangoScheduleSource):
        assert await source.get_schedules() == []

    async def test_returns_all_rows(self, source: DjangoScheduleSource):
        await source.add_schedule(make_task(schedule_id="a"))
        await source.add_schedule(make_task(schedule_id="b"))

        schedules = await source.get_schedules()

        assert {s.schedule_id for s in schedules} == {"a", "b"}
        assert all(isinstance(s, ScheduledTask) for s in schedules)

    async def test_maps_all_fields(self, source: DjangoScheduleSource):
        await source.add_schedule(make_task())

        (task,) = await source.get_schedules()

        assert task.model_dump() == IsPartialDict(
            schedule_id="sched-1",
            task_name="app:my_task",
            labels={"queue": "default"},
            args=[1, "two"],
            kwargs={"key": "value"},
            cron="0 * * * *",
        )

    async def test_empty_json_fields_default_to_empty_containers(self, source: DjangoScheduleSource):
        # Model JSON columns are NOT NULL with list/dict defaults, so an empty
        # payload must round-trip as [] / {} rather than None.
        await TaskiqTaskSchedule.objects.acreate(
            schedule_id="empty",
            task_name="app:t",
            cron="0 * * * *",
        )

        (task,) = await source.get_schedules()

        assert task.args == []
        assert task.kwargs == {}
        assert task.labels == {}


@pytest.mark.django_db(transaction=True)
class TestDeleteSchedule:
    async def test_deletes_matching_row(self, source: DjangoScheduleSource):
        await source.add_schedule(make_task(schedule_id="a"))
        await source.add_schedule(make_task(schedule_id="b"))

        await source.delete_schedule("a")

        remaining = [s.schedule_id for s in await source.get_schedules()]
        assert remaining == ["b"]

    async def test_missing_id_is_noop(self, source: DjangoScheduleSource):
        await source.add_schedule(make_task(schedule_id="a"))

        await source.delete_schedule("does-not-exist")

        assert await TaskiqTaskSchedule.objects.account() == 1


@pytest.mark.django_db(transaction=True)
class TestPostSend:
    async def test_one_shot_task_is_deleted(self, source: DjangoScheduleSource):
        run_at = datetime(2030, 1, 1, tzinfo=timezone.utc)
        await source.add_schedule(make_task(cron=None, time=run_at))

        task = make_task(cron=None, time=run_at)
        await source.post_send(task)

        assert await TaskiqTaskSchedule.objects.account() == 0

    async def test_recurring_task_is_kept(self, source: DjangoScheduleSource):
        await source.add_schedule(make_task())  # cron-based, time is None

        await source.post_send(make_task())

        assert await TaskiqTaskSchedule.objects.account() == 1


@pytest.mark.django_db(transaction=True)
class TestRoundTrip:
    async def test_add_then_get_preserves_task(self, source: DjangoScheduleSource):
        original = make_task(cron=None, interval=300, cron_offset=None)

        await source.add_schedule(original)
        (restored,) = await source.get_schedules()

        assert restored.model_dump() == IsPartialDict(
            schedule_id=original.schedule_id,
            task_name=original.task_name,
            args=original.args,
            kwargs=original.kwargs,
            labels=original.labels,
            interval=original.interval,
        )
