# NovelCreatetor

## Environment
- Python virtualenv: `C:\Users\konishi\.virtualenvs\NovelCreatetor\Scripts\python.exe`
- DB: SQLite
- Default DB file: `C:\Users\konishi\PycharmProjects\NovelCreatetor\instance\app.db`

## Install
```powershell
C:\Users\konishi\.virtualenvs\NovelCreatetor\Scripts\python.exe -m pip install Flask Flask-SQLAlchemy Flask-Migrate Flask-Session requests pytest
```

## Run
Project root: `C:\Users\konishi\PycharmProjects\NovelCreatetor`

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
DATABASE_URL=sqlite:///C:/Users/konishi/PycharmProjects/NovelCreatetor/instance/app.db
STORAGE_ROOT=C:/Users/konishi/PycharmProjects/NovelCreatetor/storage
```

```powershell
cd C:\Users\konishi\PycharmProjects\NovelCreatetor
C:\Users\konishi\.virtualenvs\NovelCreatetor\Scripts\python.exe -m flask --app app:create_app run --debug
```

Health check:

```powershell
curl http://127.0.0.1:5000/health
```

## Flask Migration
This repository already uses `migrations\` for manual SQL files, so Flask-Migrate should use a separate directory such as `flask_migrations`.

First-time initialization:

```powershell
cd C:\Users\konishi\PycharmProjects\NovelCreatetor
C:\Users\konishi\.virtualenvs\NovelCreatetor\Scripts\python.exe -m flask --app app:create_app db init flask_migrations
```

Create a migration:

```powershell
C:\Users\konishi\.virtualenvs\NovelCreatetor\Scripts\python.exe -m flask --app app:create_app db migrate -d flask_migrations -m "create initial tables"
```

Apply migrations:

```powershell
C:\Users\konishi\.virtualenvs\NovelCreatetor\Scripts\python.exe -m flask --app app:create_app db upgrade -d flask_migrations
```

Rollback one step if needed:

```powershell
C:\Users\konishi\.virtualenvs\NovelCreatetor\Scripts\python.exe -m flask --app app:create_app db downgrade -d flask_migrations
```

## Create Initial User
```powershell
cd C:\Users\konishi\PycharmProjects\NovelCreatetor
C:\Users\konishi\.virtualenvs\NovelCreatetor\Scripts\python.exe -m flask --app app:create_app create-user
```

Example:

```powershell
C:\Users\konishi\.virtualenvs\NovelCreatetor\Scripts\python.exe -m flask --app app:create_app create-user --email admin@example.com --display-name admin --password your-password
```

## Notes
- `instance\` and `storage\` are created automatically at startup.
- Project-root `.env` is loaded automatically at startup if present.
- `/health` checks both HTTP response and SQLite connectivity.
- `migrations\20260419_add_character_image_rule.sql` remains as a manual reference SQL file.

## GPT Image 1.5 Diagnostic
Use this script to verify whether your current API key supports `gpt-image-1.5` on both `/images/generations` and `/images/edits`.

```powershell
cd C:\Users\konishi\PycharmProjects\NovelCreatetor
C:\Users\konishi\.virtualenvs\NovelCreatetor\Scripts\python.exe .\scripts\verify_gpt_image_1_5_edits.py --image C:\path\to\reference.png
```

If `generations` succeeds but `edits` returns `Value must be 'dall-e-2'`, the limitation is coming from the current API environment rather than this app.
