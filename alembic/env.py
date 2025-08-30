from logging.config import fileConfig

from alembic import context
from sqlmodel import SQLModel

from app.database import engine

import app.models.user  # noqa
import app.models.project  # noqa
import app.models.chat_message  # noqa
import app.models.state_machine  # noqa
import app.models.requirement  # noqa
import app.models.sample_file  # noqa
import app.models.sample_requirement  # noqa

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata

def run_migrations_offline() -> None:
    url = engine.url.render_as_string(hide_password=False)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
