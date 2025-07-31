import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config
from sqlalchemy import pool

# Add the parent directory of 'migrations' to the Python path
sys.path.insert(0, os.path.realpath(os.path.join(os.path.dirname(__file__), '..')))

# Import the main Flask app and the BaseModel
from src.main import app
from src.models.base import BaseModel

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the target metadata using the BaseModel
target_metadata = BaseModel.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = app.config.get('SQLALCHEMY_DATABASE_URI')
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    with app.app_context():
        connectable = app.extensions['migrate'].db.get_engine()

        with connectable.connect() as connection:
            context.configure(
                connection=connection, target_metadata=target_metadata
            )

            with context.begin_transaction():
                context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()