"""add preferences column to users

Revision ID: 0001_add_preferences
Revises: 
Create Date: 2025-11-19 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_add_preferences'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('users', sa.Column('preferences', sa.JSON(), nullable=True))


def downgrade():
    op.drop_column('users', 'preferences')
