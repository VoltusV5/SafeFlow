"""Add ENUMs to models

Revision ID: b789a9fd035d
Revises: a789a9fd035d
Create Date: 2026-07-12 10:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b789a9fd035d'
down_revision: Union[str, None] = 'a789a9fd035d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # We are using native_enum=False, so Enum fields are mapped to VARCHAR.
    # The existing columns are already VARCHAR, so no schema changes are strictly necessary
    # for SQLite or Postgres. SQLAlchemy will handle validation at the application level.
    pass


def downgrade() -> None:
    pass
