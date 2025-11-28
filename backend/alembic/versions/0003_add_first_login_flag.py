"""add first login flag

Revision ID: 0003_add_first_login_flag
Revises: 0002_add_model_parameters
Create Date: 2025-11-24 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0003_add_first_login_flag"
down_revision = "0002_add_model_parameters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("first_login_completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.execute("UPDATE users SET first_login_completed = true")


def downgrade() -> None:
    op.drop_column("users", "first_login_completed")
