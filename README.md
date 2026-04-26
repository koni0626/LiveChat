# LaplaceCity

## Environment
- Python: 3.10+
- DB: SQLite
- Default DB file: `instance/app.db`

## Install
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Run
You can place runtime settings in a project-root `.env` file. Start from `.env.example`.

Example:

```powershell
Copy-Item .env.example .env
```

Main keys:

```text
OPENAI_API_KEY=sk-...
TEXT_AI_MODEL=gpt-5.4-mini
IMAGE_AI_MODEL=gpt-image-2
IMAGE_DEFAULT_QUALITY=medium
DATABASE_URL=sqlite:///instance/app.db
STORAGE_ROOT=storage
LETTER_COOLDOWN_MINUTES=360
```

```powershell
python -m flask --app app:create_app run --debug --port 5003
```

Health check:

```powershell
curl http://127.0.0.1:5003/health
```

## Docker
Build the image:

```powershell
docker build -t laplace-city .
```

Create a Docker env file:

```powershell
Copy-Item .env.docker.example .env.docker
```

Edit `.env.docker` and set `OPENAI_API_KEY` and `SECRET_KEY`, then run:

```powershell
docker run --rm -p 5003:5003 --env-file .env.docker -v ${PWD}/instance:/app/instance -v ${PWD}/storage:/app/storage laplace-city
```

Open:

```text
http://127.0.0.1:5003
```

Create the first superuser inside a running container:

```powershell
docker ps
docker exec -it <container_id> python -m flask create-user --role superuser
```

The container runs `flask db upgrade -d flask_migrations` automatically on startup. Set `SKIP_DB_UPGRADE=1` only when you intentionally want to skip migrations.

Gunicorn timeout is set through environment variables because image generation and AI responses can take longer than the Gunicorn default timeout:

```text
GUNICORN_WORKERS=2
GUNICORN_TIMEOUT=300
GUNICORN_GRACEFUL_TIMEOUT=30
```

For local testing, you can shorten the in-app letter cooldown in `.env`:

```text
LETTER_COOLDOWN_MINUTES=1
```

## Flask Migration
This repository already uses `migrations\` for manual SQL files, so Flask-Migrate should use a separate directory such as `flask_migrations`.

First-time initialization:

```powershell
python -m flask --app app:create_app db init flask_migrations
```

Create a migration:

```powershell
python -m flask --app app:create_app db migrate -d flask_migrations -m "create initial tables"
```

Apply migrations:

```powershell
python -m flask --app app:create_app db upgrade -d flask_migrations
```

Rollback one step if needed:

```powershell
python -m flask --app app:create_app db downgrade -d flask_migrations
```

## Create Initial User
```powershell
python -m flask --app app:create_app create-user
```

Example:

```powershell
python -m flask --app app:create_app create-user --email admin@example.com --display-name admin --password your-password --role superuser
```

## Notes
- `instance\` and `storage\` are created automatically at startup.
- Project-root `.env` is loaded automatically at startup if present.
- `/health` checks both HTTP response and SQLite connectivity.
- `migrations\20260419_add_character_image_rule.sql` remains as a manual reference SQL file.

## GPT Image 1.5 Diagnostic
Use this script to verify whether your current API key supports `gpt-image-1.5` on both `/images/generations` and `/images/edits`.

```powershell
python .\scripts\verify_gpt_image_1_5_edits.py --image C:\path\to\reference.png
```

If `generations` succeeds but `edits` returns `Value must be 'dall-e-2'`, the limitation is coming from the current API environment rather than this app.
