from django.db import models


class TaskiqSchedule(models.Model):
    # task_name = models.CharField(max_lenght=100)
    # schedule = models.JSONField()
    # created_at = models.DateTimeField(auto_now_add=True)
    # updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        managed = False
        verbose_name = 'Taskiq schedule'
        verbose_name_plural = 'Taskiq schedules'
