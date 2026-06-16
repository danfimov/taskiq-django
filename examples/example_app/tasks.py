import asyncio

from django.contrib.auth.models import User
from taskiq import async_shared_broker


@async_shared_broker.task(
    "solve_all_problems",
    schedule=[{"cron": "*/5 * * * *", "args": ['Cron run']}]
)
async def best_task_ever(rundom_argument: str) -> None:
    """Solve all problems in the world."""
    print(f'Wow, I get "{rundom_argument}"')
    await asyncio.sleep(2)
    print("All problems are solved!")


@async_shared_broker.task("list_users")
async def list_users() -> None:
    async for user in User.objects.all():
        print(user.username)
