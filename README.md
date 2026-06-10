# taskiq-django

Django integration for [Taskiq](https://taskiq-python.github.io/).

`taskiq-django` lets you run a Taskiq broker alongside a Django project and persist scheduled tasks in your Django database.
It ships with:

- `DjangoScheduleSource` — a `taskiq.ScheduleSource` backed by the Django ORM.
- A Django admin for adding, editing and deleting schedules through the web UI.

The package itself is broker-agnostic — pair it with any Taskiq broker (`AsyncpgBroker`, `RedisBroker`, `KafkaBroker`, etc.).
The `examples/` folder uses [taskiq-postgres](https://github.com/danfimov/taskiq-postgres/) on top of PostgreSQL.

## Installation

```bash
pip install taskiq-django
```

Add the app to `INSTALLED_APPS` so its model and admin are registered:

```python
# settings.py
INSTALLED_APPS = [
    # ...
    "taskiq_django",
]
```

Then apply the migration that creates the `taskiq_schedules` table:

```bash
python manage.py migrate taskiq_django
```

## Using Taskiq with Django

Taskiq broker and scheduler are async, while Django historically is sync. The cleanest way to host both in a single process
is to serve Django over ASGI and let an ASGI server (`granian` or `uvicorn` for example) drive the broker lifecycle through
Starlette's `lifespan` hook.

The recipe below mirrors the one used in [`examples/example_app`](examples/example_app/) of this repository.

### Default Django application

A standard Django ASGI entry point looks like this:

```python
# asgi.py
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "example_app.settings")
application = get_asgi_application()
```

This is enough to serve Django through any ASGI server, but it has no place to plug a Taskiq broker into — Django's ASGI app
does not expose `lifespan` events.

### Serving Django via Starlette

Wrap the Django ASGI app in a [Starlette](https://www.starlette.io/) application and mount it at `/`. Starlette supports
`lifespan`, makes static files easy, and lets us add ASGI middleware around Django:

```python
# asgi.py
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "example_app.settings")
django_asgi = get_asgi_application()

from starlette.applications import Starlette
from starlette.routing import Mount

application = Starlette(
    routes=(
        Mount("/", django_asgi),
    ),
)
```

> Set `DJANGO_SETTINGS_MODULE` and call `get_asgi_application()` **before** importing anything that touches Django models
> (including `taskiq_django`). Otherwise `django.apps.AppRegistryNotReady` will fire at import time.

### Serving static files with Starlette

Collect Django's static files into a folder and serve it via `StaticFiles`. In your Django settings:

```python
# settings.py
STATIC_URL = "static/"
STATIC_ROOT = "static/"
```

Then add a `Mount` in front of Django:

```python
# asgi.py
from starlette.staticfiles import StaticFiles

application = Starlette(
    routes=(
        Mount("/static", StaticFiles(directory="static"), name="static"),
        Mount("/", django_asgi),
    ),
)
```

Run `python manage.py collectstatic` once so admin CSS/JS appears under `static/`.

### Broker and scheduler lifespan

Construct the broker and scheduler at module level, and use a Starlette `lifespan` to start and stop them with the process:

```python
# asgi.py
from contextlib import asynccontextmanager
from taskiq import TaskiqScheduler, async_shared_broker
from taskiq_pg.asyncpg import AsyncpgBroker

from taskiq_django import DjangoScheduleSource

DSN = "postgres://taskiq_django:look_in_vault@localhost:5432/taskiq_django"
broker = AsyncpgBroker(dsn=DSN)
async_shared_broker.default_broker(broker)

scheduler = TaskiqScheduler(
    broker=broker,
    sources=[DjangoScheduleSource()],
)


@asynccontextmanager
async def broker_lifespan(app):
    await broker.startup()
    for source in scheduler.sources:
        await source.startup()
    try:
        yield
    finally:
        for source in scheduler.sources:
            await source.shutdown()
        await broker.shutdown()


application = Starlette(
    routes=(...),
    lifespan=broker_lifespan,
)
```

### Injecting broker and scheduler into requests

If you want Django views (including the schedules admin) to reach the broker or the scheduler, add a small ASGI middleware
that puts them on the request scope. The Django `request.scope` dict is the same `scope` Starlette passed down, so values
land directly on `request.scope["broker"]` / `request.scope["scheduler"]`:

```python
# asgi.py
from starlette.middleware import Middleware


class InjectBrokerMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            scope["broker"] = broker
            scope["scheduler"] = scheduler
        await self.app(scope, receive, send)


application = Starlette(
    routes=(...),
    lifespan=broker_lifespan,
    middleware=[Middleware(InjectBrokerMiddleware)],
)
```

### Full example

```python
# asgi.py
import os
from contextlib import asynccontextmanager

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "example_app.settings")
django_asgi = get_asgi_application()

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles
from taskiq import TaskiqScheduler, async_shared_broker
from taskiq_pg.asyncpg import AsyncpgBroker

from taskiq_django import DjangoScheduleSource

DSN = "postgres://taskiq_django:look_in_vault@localhost:5432/taskiq_django"
broker = AsyncpgBroker(dsn=DSN)
async_shared_broker.default_broker(broker)

scheduler = TaskiqScheduler(
    broker=broker,
    sources=[DjangoScheduleSource()],
)


@asynccontextmanager
async def broker_lifespan(app):
    await broker.startup()
    for source in scheduler.sources:
        await source.startup()
    try:
        yield
    finally:
        for source in scheduler.sources:
            await source.shutdown()
        await broker.shutdown()


class InjectBrokerMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            scope["broker"] = broker
            scope["scheduler"] = scheduler
        await self.app(scope, receive, send)


application = Starlette(
    routes=(
        Mount("/static", StaticFiles(directory="static"), name="static"),
        Mount("/", django_asgi),
    ),
    lifespan=broker_lifespan,
    middleware=[Middleware(InjectBrokerMiddleware)],
)
```

Run the web process with any ASGI server, e.g. Granian:

```bash
granian example_app.asgi:application --interface asgi --reload
```

## Defining tasks

Use `async_shared_broker.task` so tasks are not bound to a concrete broker at import time — the broker is attached at runtime
via `async_shared_broker.default_broker(broker)`:

```python
# example_app/tasks.py
from taskiq import async_shared_broker


@async_shared_broker.task("solve_all_problems")
async def best_task_ever(message: str) -> None:
    print(f'Got "{message}"')
```

To make sure tasks are discovered and registered with the broker, use Taskiq's filesystem discovery flag (`--fs-discover`)
when starting the worker, or import the tasks module from `asgi.py`.

## Persistent schedules with `DjangoScheduleSource`

`DjangoScheduleSource` stores `ScheduledTask` records in the Django database via the `taskiq_schedules` table. Plug it into
your scheduler:

```python
from taskiq import TaskiqScheduler
from taskiq_django import DjangoScheduleSource

scheduler = TaskiqScheduler(
    broker=broker,
    sources=[DjangoScheduleSource()],
)
```

Schedules can now be managed through the Django admin: `/admin/taskiq_django/taskiqtaskschedule/` exposes list / add /
change / delete views. Each action routes through the source's `add_schedule` / `delete_schedule` methods, so any side
effects you add by subclassing `DjangoScheduleSource` will fire from the admin too.

A schedule row carries the full `ScheduledTask` payload — `task_name`, `args`, `kwargs`, `labels`, plus the schedule
definition (`cron` + optional `cron_offset`, or `time` for one-shots, or `interval` in seconds). Exactly one of `cron` /
`time` / `interval` must be set.

> `DjangoScheduleSource.startup()` does **not** truncate or seed the table — the admin is treated as the source of truth.
> If you want to sync schedules declared on `@task(schedule=[...])` labels into the database, do it explicitly from a
> one-off script or a management command.

## Running the worker and the scheduler

Both the worker and the scheduler import the broker and the scheduler objects from `asgi.py`:

```bash
# worker
taskiq worker example_app.asgi:broker --fs-discover

# scheduler
taskiq scheduler example_app.asgi:scheduler --fs-discover
```

Because `asgi.py` calls `get_asgi_application()` at import time, Django is fully configured by the time the worker or
scheduler process touches any ORM code — no extra bootstrapping needed.

If you'd rather keep `asgi.py` web-only, move the broker/scheduler/`DJANGO_SETTINGS_MODULE` setup into a dedicated
`broker.py` module and call `django.setup()` at the top of it; then point Taskiq at `example_app.broker:broker` instead.

## Accessing the Django ORM from a Taskiq task

Inside a worker process, Django ORM is fully available — both sync and async APIs:

```python
from django.contrib.auth.models import User
from taskiq import async_shared_broker


@async_shared_broker.task("list_users")
async def list_users() -> None:
    async for user in User.objects.all():
        print(user.username)
```

When the worker imports `example_app.asgi:broker`, the module-level `get_asgi_application()` call has already run
`django.setup()`, so model imports work immediately.

## Local development

The example project under `examples/` ships with a `Makefile`:

```bash
make run_infra       # docker compose up -d postgres
make run             # granian + Starlette + Django
make run_worker      # taskiq worker
make run_scheduler   # taskiq scheduler
```
