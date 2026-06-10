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

from example_app.tasks import best_task_ever
from taskiq_django import DjangoScheduleSource

dsn = "postgres://taskiq_django:look_in_vault@localhost:5432/taskiq_django"
broker = AsyncpgBroker(dsn=dsn)
async_shared_broker.default_broker(broker)

scheduler = TaskiqScheduler(
    broker=broker,
    sources=[DjangoScheduleSource()],
)


@asynccontextmanager
async def broker_lifespan(app):
    await broker.startup()
    for schedule_source in scheduler.sources:
        await schedule_source.startup()
    await best_task_ever.kiq("Hello, world")
    try:
        yield
    finally:
        for schedule_source in scheduler.sources:
            await schedule_source.shutdown()
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
    middleware=[
        Middleware(InjectBrokerMiddleware),
    ],
)
