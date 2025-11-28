"""add model_parameters table

Revision ID: 0002_add_model_parameters
Revises: 0001_add_preferences
Create Date: 2025-11-19 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0002_add_model_parameters'
down_revision = '0001_add_preferences'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'model_parameters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('knn_n', sa.Integer(), nullable=False, server_default='15'),
        sa.Column('kr_bandwidth', sa.Float(), nullable=False, server_default='1.25'),
        sa.Column('lwlr_tau', sa.Float(), nullable=False, server_default='3.0'),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('model_parameters')
