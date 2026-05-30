"""Alembic environment configured for the async SQLAlchemy engine.

The database URL and metadata come from the application so migrations stay in
sync with the app's configuration and models.
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.database import Base

# Import every module's models so Base.metadata is complete for autogenerate.
# Keep this list in sync as modules add models.
from app.modules.adaptive import models as _adaptive_models  # noqa: F401
from app.modules.ai import models as _ai_models  # noqa: F401
from app.modules.attendance import models as _attendance_models  # noqa: F401
from app.modules.blueprint import models as _blueprint_models  # noqa: F401
from app.modules.content import models as _content_models  # noqa: F401
from app.modules.courses import models as _courses_models  # noqa: F401
from app.modules.enrollment import models as _enrollment_models  # noqa: F401
from app.modules.iam import models as _iam_models  # noqa: F401
from app.modules.integrations import models as _integrations_models  # noqa: F401
from app.modules.notifications import models as _notifications_models  # noqa: F401
from app.modules.projects import models as _projects_models  # noqa: F401
from app.modules.stages import models as _stages_models  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
