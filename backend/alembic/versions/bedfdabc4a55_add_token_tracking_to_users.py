"""add_token_tracking_to_users

Revision ID: bedfdabc4a55
Revises: 0002_add_learning_mode_tables
Create Date: 2025-12-24 12:40:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'bedfdabc4a55'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    # Add token tracking columns to users table
    op.add_column('users', sa.Column('tokens_used', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('tokens_limit', sa.Integer(), nullable=False, server_default='150000'))
    op.add_column('users', sa.Column('tokens_reset_at', sa.DateTime(), nullable=True))


def downgrade():
    # Remove token tracking columns
    op.drop_column('users', 'tokens_reset_at')
    op.drop_column('users', 'tokens_limit')
    op.drop_column('users', 'tokens_used')
