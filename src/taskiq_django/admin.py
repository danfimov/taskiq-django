from asgiref.sync import async_to_sync
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import URLPattern, path, reverse

from taskiq_django.forms import TaskiqTaskScheduleForm
from taskiq_django.models import TaskiqTaskSchedule
from taskiq_django.schedule_source import DjangoScheduleSource

FIELDSETS = [
    (None, {"fields": ["schedule_id", "task_name"]}),
    ("Schedule", {"fields": ["cron", "cron_offset", "time", "interval"]}),
    ("Payload", {"fields": ["args", "kwargs", "labels"], "classes": ["collapse"]}),
]


def _get_source(request) -> DjangoScheduleSource:
    scheduler = request.scope["scheduler"]
    for source in scheduler.sources:
        if isinstance(source, DjangoScheduleSource):
            return source
    raise RuntimeError("DjangoScheduleSource is not registered in the scheduler.")


@admin.register(TaskiqTaskSchedule)
class TaskiqTaskScheduleAdmin(admin.ModelAdmin):
    def get_urls(self) -> list[URLPattern]:
        urls = super().get_urls()
        wrap = self.admin_site.admin_view
        custom_urls = [
            path(
                "",
                wrap(self.external_list_view),
                name="taskiq_django_taskiqtaskschedule_changelist",
            ),
            path(
                "add/",
                wrap(self.external_add_view),
                name="taskiq_django_taskiqtaskschedule_add",
            ),
            path(
                "<path:object_id>/change/",
                wrap(self.external_change_view),
                name="taskiq_django_taskiqtaskschedule_change",
            ),
            path(
                "<path:object_id>/delete/",
                wrap(self.external_delete_view),
                name="taskiq_django_taskiqtaskschedule_delete",
            ),
        ]
        return custom_urls + urls

    def external_list_view(self, request):
        source = _get_source(request)
        tasks = async_to_sync(source.get_schedules)()
        rows = [
            {
                "id": task.schedule_id,
                "task_name": task.task_name,
                "schedule": task.cron or task.time or (task.interval and f"every {task.interval}s"),
                "created_at": None,
                "updated_at": None,
            }
            for task in tasks
        ]
        context = {
            **self.admin_site.each_context(request),
            "title": self.model._meta.verbose_name_plural,
            "opts": self.model._meta,
            "rows": rows,
        }
        return TemplateResponse(request, "taskiq_django/list_view.html", context)

    def external_add_view(self, request):
        source = _get_source(request)
        task_names = list(request.scope["broker"].get_all_tasks().keys())
        if request.method == "POST":
            form = TaskiqTaskScheduleForm(request.POST, task_names=task_names)
            if form.is_valid():
                async_to_sync(source.add_schedule)(form.to_scheduled_task())
                messages.success(request, "Schedule created.")
                return HttpResponseRedirect(
                    reverse("admin:taskiq_django_taskiqtaskschedule_changelist")
                )
        else:
            form = TaskiqTaskScheduleForm(task_names=task_names)
        return self._render_form(request, form, title="Add taskiq schedule", object_id=None)

    def external_change_view(self, request, object_id):
        source = _get_source(request)
        task_names = list(request.scope["broker"].get_all_tasks().keys())
        if request.method == "POST":
            form = TaskiqTaskScheduleForm(request.POST, task_names=task_names)
            if form.is_valid():
                async_to_sync(source.add_schedule)(form.to_scheduled_task())
                messages.success(request, "Schedule updated.")
                return HttpResponseRedirect(
                    reverse("admin:taskiq_django_taskiqtaskschedule_changelist")
                )
        else:
            task = self._find_schedule(source, object_id)
            if task is None:
                messages.error(request, f"Schedule {object_id} not found.")
                return HttpResponseRedirect(
                    reverse("admin:taskiq_django_taskiqtaskschedule_changelist")
                )
            form = TaskiqTaskScheduleForm.from_scheduled_task(task, task_names=task_names)
        return self._render_form(
            request, form, title="Change taskiq schedule", object_id=object_id
        )

    def external_delete_view(self, request, object_id):
        if request.method == "POST":
            source = _get_source(request)
            async_to_sync(source.delete_schedule)(object_id)
            messages.success(request, "Schedule deleted.")
            return HttpResponseRedirect(
                reverse("admin:taskiq_django_taskiqtaskschedule_changelist")
            )
        context = {
            **self.admin_site.each_context(request),
            "title": "Delete taskiq schedule",
            "opts": self.model._meta,
            "object_id": object_id,
        }
        return TemplateResponse(request, "taskiq_django/delete_confirmation.html", context)

    def _render_form(self, request, form, *, title, object_id):
        adminform = helpers.AdminForm(
            form,
            fieldsets=FIELDSETS,
            prepopulated_fields={},
            readonly_fields=[],
            model_admin=self,
        )
        context = {
            **self.admin_site.each_context(request),
            "title": title,
            "opts": self.model._meta,
            "object_id": object_id,
            "original": {"pk": object_id} if object_id else None,
            "adminform": adminform,
            "errors": helpers.AdminErrorList(form, []),
            "media": self.media + adminform.media,
            "is_popup": False,
            "save_as": False,
            "save_on_top": False,
            "show_save": True,
            "show_save_as_new": False,
            "show_save_and_add_another": False,
            "show_save_and_continue": False,
            "show_close": False,
            "show_delete_link": object_id is not None,
            "can_change": True,
            "add": object_id is None,
            "change": object_id is not None,
            "has_view_permission": True,
            "has_add_permission": True,
            "has_change_permission": True,
            "has_delete_permission": True,
            "has_file_field": False,
            "has_editable_inline_admin_formsets": False,
            "inline_admin_formsets": [],
        }
        return TemplateResponse(request, "taskiq_django/change_form.html", context)

    @staticmethod
    def _find_schedule(source: DjangoScheduleSource, schedule_id: str):
        for task in async_to_sync(source.get_schedules)():
            if task.schedule_id == schedule_id:
                return task
        return None
