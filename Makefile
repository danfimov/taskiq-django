run:
	@(cd examples && granian example_app.asgi:application --interface asgi --reload)

run_worker:
	@(cd examples && taskiq worker example_app.asgi:broker --fs-discover)

run_scheduler:
	@(cd examples && taskiq scheduler example_app.asgi:scheduler --fs-discover)

run_infra:
	docker compose up -d postgres

ruff:
	@uv run ruff check .

ty:
	@uv run ty check .
