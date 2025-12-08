"""remove first_login_completed feature

Revision ID: 0011_remove_first_login
Revises: 0010_make_structure_global
Create Date: 2025-12-06

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0011_remove_first_login'
down_revision = '0010_make_structure_global'
branch_labels = None
depends_on = None


def upgrade():
    # Drop first_login_completed column from users table
    op.execute('ALTER TABLE users DROP COLUMN IF EXISTS first_login_completed')


def downgrade():
    # Add back first_login_completed column
    op.add_column('users', 
                  sa.Column('first_login_completed', sa.Boolean(), 
                           nullable=False, server_default=sa.text('false')))
