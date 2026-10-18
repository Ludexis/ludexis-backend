<p align="center">
  <img src="https://raw.githubusercontent.com/Ludexis/Ludexis/main/docs/Ludexis.webp" width="320" alt="Ludexis">
</p>

<h3 align="center">Ludexis Backend</h3>

<p align="center">
  The API, scanner and background workers behind <a href="https://github.com/Ludexis/Ludexis">Ludexis</a>, a self-hosted catalogue for game archives.
</p>

<p align="center">
  <a href="https://github.com/Ludexis/ludexis-backend/actions/workflows/ci.yml"><img src="https://github.com/Ludexis/ludexis-backend/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <img src="https://img.shields.io/badge/Python-3.12-6D3DF5?logo=python&logoColor=white" alt="Python 3.12">
  <img src="https://img.shields.io/badge/FastAPI-0.143-6D3DF5?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/PostgreSQL-16-6D3DF5?logo=postgresql&logoColor=white" alt="PostgreSQL 16">
  <img src="https://img.shields.io/badge/Celery-5.4-6D3DF5?logo=celery&logoColor=white" alt="Celery">
  <img src="https://img.shields.io/badge/License-MIT-6D3DF5" alt="MIT License">
</p>

---

This repository holds the server side of Ludexis:

- a **FastAPI** REST API for the web app: authentication, libraries, games, collections, franchises, users, roles and administration;
- the **library scanner**, which finds games in folders and archives and records every file and version;
- **metadata providers** for VNDB, IGDB and Steam, plus SteamGridDB artwork, and a loader for extra providers from a folder;
- **Celery workers and a scheduler** for scans, metadata refresh, artwork downloads and scheduled tasks;
- **Alembic** migrations for the PostgreSQL schema.

The web app lives in [ludexis-frontend](https://github.com/Ludexis/ludexis-frontend). To run the whole stack, use the Docker Compose setup in the [main repository](https://github.com/Ludexis/Ludexis).

## Getting started

**Requirements:** Python 3.12, PostgreSQL 16 and Redis 7.

The quickest way to get the database and Redis is the development compose file in the main repository:

```bash
git clone --recurse-submodules https://github.com/Ludexis/Ludexis.git
cd Ludexis
docker compose -f docker-compose.dev.yml up -d   # PostgreSQL on 5432, Redis on 6379 (localhost only)
cd backend
```

Or start both directly:

```bash
docker run -d --name ludexis-db -p 127.0.0.1:5432:5432 \
  -e POSTGRES_USER=ludexis -e POSTGRES_PASSWORD=ludexis -e POSTGRES_DB=ludexis postgres:16
docker run -d --name ludexis-redis -p 127.0.0.1:6379:6379 redis:7
```

Then install and run the API:

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                 # add TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET for IGDB
alembic upgrade head
uvicorn main:app --reload            # http://localhost:8000, interactive API docs at /docs
```

In two more terminals:

```bash
celery -A app.tasks.celery_app worker --loglevel=info   # add --pool=solo on Windows
celery -A app.tasks.celery_app beat --loglevel=info     # scheduled tasks
```

On first start an `admin` / `admin` account is created; it must choose a new password at its first sign-in.

## Configuration

Settings are read from the environment or `.env` (see [`.env.example`](.env.example)).

| Variable | Purpose |
| -------- | ------- |
| `DATABASE_URL` | PostgreSQL connection (`postgresql+psycopg://...`). Left unset, it is built from `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_HOST` (default `db`) and `POSTGRES_PORT` |
| `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | Redis for the job queue and results (default `redis://redis:6379/0`; the Celery URLs default to `REDIS_URL`) |
| `JWT_SECRET_KEY` | Token signing secret. Left empty, one is generated into `CONFIG_DIR` |
| `CONFIG_DIR` | Where the generated secret is kept |
| `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` | Session lifetimes |
| `JOB_MAX_RETRIES`, `JOB_RETRY_BACKOFF_MAX` | Retry policy for background jobs |
| `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET` | IGDB access ([dev.twitch.tv](https://dev.twitch.tv/console)) |
| `STEAMGRIDDB_API_KEY` | Optional extra artwork source |
| `PROVIDER_PLUGINS_DIR` | Folder of extra metadata provider modules (`*.py`), loaded at startup |
| `ARTWORK_STORAGE_PATH` | Where downloaded artwork is stored |
| `CORS_ORIGINS` | Allowed web app origins, comma separated |
| `DEFAULT_ADMIN_USERNAME`, `DEFAULT_ADMIN_PASSWORD` | Account created on a database without users |

## Project layout

```text
app/
  api/            FastAPI routers, one module per resource
  core/           settings, authentication, access rules, logging, metrics, rate limits
  db/             engine and session setup
  models/         SQLAlchemy models
  schemas/        Pydantic request and response models
  repositories/   database queries
  services/       business logic: scanning, metadata, artwork, grouping, jobs
  providers/      metadata providers (VNDB, IGDB, Steam, SteamGridDB) and the plugin loader
  edge/           the edge device process (python -m app.edge) and its install files (bundle/)
  tasks/          Celery app, job runner and task modules
  utils/          shared helpers
alembic/          database migrations
bin/ludexis       container entry point: server, worker, beat, edge, health <role>
scripts/          admin tools: reset_password, seed_demo
tests/            pytest suite
main.py           application entry point
```

## Tests

The suite runs against a real PostgreSQL database called `ludexis_ci` (override with `TEST_DATABASE_URL`):

```bash
docker exec ludexis-db createdb -U ludexis ludexis_ci   # once
pytest -q
```

Every pull request runs the migrations and the full suite in CI.

## Database migrations

```bash
alembic revision --autogenerate -m "describe the change"   # after editing a model
alembic upgrade head
```

The container runs `alembic upgrade head` before starting the API, so deployments migrate on their own.

## Docker image

```bash
docker build -t ludexis-backend .
```

Pushes to `main` publish `ghcr.io/ludexis/ludexis-backend:latest` for `linux/amd64` and `linux/arm64`. A `v1.2.3` tag also publishes `:1.2.3` and `:1.2`. The same image runs the API, the worker, the scheduler and edge devices; only the command differs: `ludexis server`, `ludexis worker`, `ludexis beat` or `ludexis edge` (`ludexis health <role>` for health checks).

Admin tools run inside the container:

```bash
docker compose exec backend python -m scripts.reset_password <username>
```

## Contributing

Bug reports, ideas and pull requests are welcome. Read the [contributing guide](https://github.com/Ludexis/.github/blob/main/CONTRIBUTING.md) first. In short: branch from `main`, keep each change focused, add or update tests, and make sure `pytest` passes.

## Maintainer

**Rupankar Majumdar ([@InvictusRex](https://github.com/InvictusRex))**

## License

[MIT](LICENSE)
