from django.db import models


class TaskiqTaskSchedule(models.Model):
    schedule_id = models.CharField(max_length=64, primary_key=True)
    task_name = models.CharField(max_length=255)

    args = models.JSONField(default=list, db_default=list())
    kwargs = models.JSONField(default=dict, db_default=dict())
    labels = models.JSONField(default=dict, db_default=dict())

    cron = models.CharField(max_length=255, null=True, blank=True)
    cron_offset = models.CharField(max_length=64, null=True, blank=True)
    time = models.DateTimeField(null=True, blank=True)
    interval = models.PositiveIntegerField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Task schedule"
        verbose_name_plural = "Task schedules"
        db_table = "taskiq_schedules"

    def __str__(self) -> str:
        return f"{self.task_name} ({self.schedule_id})"
