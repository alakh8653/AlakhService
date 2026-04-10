# Alembic Migrations

This directory contains database migration scripts managed by [Alembic](https://alembic.sqlalchemy.org/).

## Setup

```bash
# Initialize Alembic (already done — only run once)
alembic init migrations
```

## Common Commands

| Command | Description |
|---------|-------------|
| `alembic revision --autogenerate -m "description"` | Auto-generate a new migration from model changes |
| `alembic upgrade head` | Apply all pending migrations |
| `alembic downgrade -1` | Roll back the last migration |
| `alembic downgrade base` | Roll back all migrations |
| `alembic current` | Show the current revision |
| `alembic history --verbose` | Show full migration history |

## Workflow

1. Make changes to SQLAlchemy models in `app/models/`.
2. Run `alembic revision --autogenerate -m "short_description"` to generate a migration.
3. Review the generated file in `migrations/versions/` and adjust if necessary.
4. Run `alembic upgrade head` to apply the migration.

## Naming Conventions

- Use lowercase snake_case for the migration description.
- Be descriptive: `add_phone_number_to_users`, `create_payments_table`.
- Each migration file is prefixed with a unique revision ID.

## Notes

- The `DATABASE_URL` in `alembic.ini` is overridden by the `ALEMBIC_DATABASE_URL` or `DATABASE_URL`
  environment variable. Make sure it is set before running migrations.
- Always review auto-generated migrations before applying them — Alembic may miss certain changes
  (e.g., column type changes, constraints).
