from datetime import datetime
from django.contrib import admin
from django.template.response import TemplateResponse
from django.urls import path, URLPattern, URLResolver
from taskiq_django.models import TaskiqSchedule


@admin.register(TaskiqSchedule)
class TaskiqScheduleAdmin(admin.ModelAdmin):
    def get_urls(self) -> list[URLResolver | URLPattern]:
        urls = super().get_urls()
        custom_urls = [
            path(
                "",
                self.admin_site.admin_view(self.external_list_view),
                name="taskiq_django_taskiqschedule_changelist",
            ),
            path(
                "<path:object_id>/change/",
                self.admin_site.admin_view(self.external_change_view),
                name="taskiq_django_taskiqschedule_change",
            ),
        ]
        return custom_urls + urls

    def external_list_view(self, request):
        rows = [
            {
                'id': 1,
                'task_name': 'Task name #1',
                'schedule': {'cron': '0 * * * *'},
                'created_at': datetime.now(),
                'updated_at': datetime.now(),
            },
            {
                'id': 2,
                'task_name': 'Task name #2',
                'schedule': {'cron': '1 * * * *'},
                'created_at': datetime.now(),
                'updated_at': datetime.now(),
            },
        ]
        context = {
            **self.admin_site.each_context(request),
            "title": self.model._meta.verbose_name_plural,
            "opts": self.model._meta,
            "rows": rows,
        }
        return TemplateResponse(
            request,
            "taskiq_django/list_view.html",
            context,
        )

    def external_change_view(self, request, object_id):
        item = {"id": object_id, "name": object_id}
        context = {
            **self.admin_site.each_context(request),
            "title": "Change taskiq schedule",
            "opts": self.model._meta,
            "object_id": object_id,
            "original": item,
            "item": item,
        }
        return TemplateResponse(
            request,
            "taskiq_django/change_form.html",
            context,
        )
