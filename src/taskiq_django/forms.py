import uuid

from django import forms
from django.contrib.admin import widgets as admin_widgets
from taskiq.scheduler.scheduled_task import ScheduledTask


class NonEmptyJSONField(forms.JSONField):
    """JSONField that treats {} and [] as valid (non-empty) values."""

    empty_values = [None, ""]


class TaskiqTaskScheduleForm(forms.Form):
    schedule_id = forms.CharField(max_length=64, required=False, widget=forms.HiddenInput)
    task_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={"class": "vTextField"}),
    )

    def __init__(self, *args, task_names: list[str] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        if task_names is not None:
            choices = [(name, name) for name in task_names]
            current = self.initial.get("task_name") or (
                self.data.get("task_name") if self.is_bound else None
            )
            if current and current not in task_names:
                choices.insert(0, (current, f"{current} (not registered)"))
            self.fields["task_name"] = forms.ChoiceField(
                choices=choices,
                widget=forms.Select,
            )
    cron = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={"class": "vTextField"}),
        help_text="Standard cron expression (e.g. '0 * * * *').",
    )
    cron_offset = forms.CharField(
        max_length=64,
        required=False,
        widget=forms.TextInput(attrs={"class": "vTextField"}),
        help_text="Timezone or offset for cron evaluation.",
    )
    time = forms.SplitDateTimeField(
        required=False,
        widget=admin_widgets.AdminSplitDateTime,
        help_text="One-shot run at this datetime (UTC).",
    )
    interval = forms.IntegerField(
        min_value=1,
        required=False,
        widget=forms.NumberInput(attrs={"class": "vIntegerField"}),
        help_text="Interval in seconds.",
    )
    args = NonEmptyJSONField(
        initial=list,
        widget=forms.Textarea(attrs={"class": "vLargeTextField", "rows": 4}),
    )
    kwargs = NonEmptyJSONField(
        initial=dict,
        widget=forms.Textarea(attrs={"class": "vLargeTextField", "rows": 4}),
    )
    labels = NonEmptyJSONField(
        initial=dict,
        widget=forms.Textarea(attrs={"class": "vLargeTextField", "rows": 4}),
    )

    def clean(self):
        cleaned = super().clean()
        if not any((cleaned.get("cron"), cleaned.get("time"), cleaned.get("interval"))):
            raise forms.ValidationError("One of cron, time or interval must be set.")
        return cleaned

    def to_scheduled_task(self) -> ScheduledTask:
        cleaned = self.cleaned_data
        return ScheduledTask(
            schedule_id=cleaned.get("schedule_id") or uuid.uuid4().hex,
            task_name=cleaned["task_name"],
            labels=cleaned.get("labels") or {},
            args=cleaned.get("args") or [],
            kwargs=cleaned.get("kwargs") or {},
            cron=cleaned.get("cron") or None,
            cron_offset=cleaned.get("cron_offset") or None,
            time=cleaned.get("time"),
            interval=cleaned.get("interval"),
        )

    @classmethod
    def from_scheduled_task(
        cls,
        task: ScheduledTask,
        *,
        task_names: list[str] | None = None,
    ) -> "TaskiqTaskScheduleForm":
        return cls(
            initial={
                "schedule_id": task.schedule_id,
                "task_name": task.task_name,
                "cron": task.cron,
                "cron_offset": task.cron_offset,
                "time": task.time,
                "interval": task.interval,
                "args": task.args,
                "kwargs": task.kwargs,
                "labels": task.labels,
            },
            task_names=task_names,
        )
