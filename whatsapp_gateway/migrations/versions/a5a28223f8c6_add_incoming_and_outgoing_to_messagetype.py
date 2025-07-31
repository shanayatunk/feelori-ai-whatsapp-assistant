"""Add incoming and outgoing to messagetype

Revision ID: a5a28223f8c6
Revises: 389fb1fa5067
Create Date: 2025-07-26 08:59:17.164782

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a5a28223f8c6'
down_revision = '389fb1fa5067'
branch_labels = None
depends_on = None


def upgrade():
    # Use op.execute to run a raw SQL command to alter the ENUM type
    op.execute("ALTER TYPE messagetype ADD VALUE IF NOT EXISTS 'incoming'")
    op.execute("ALTER TYPE messagetype ADD VALUE IF NOT EXISTS 'outgoing'")


def downgrade():
    # Downgrading is not supported for this migration
    pass