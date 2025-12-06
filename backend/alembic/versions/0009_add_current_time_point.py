"""Add current_time_point to custom_teaching_structures

Revision ID: 0009_add_current_time_point
Revises: 0008_rename_learning_documents_to_ai_insights
Create Date: 2025-12-04

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0009_add_current_time_point'
down_revision = '0008_rename_learning_documents_to_ai_insights'
branch_labels = None
depends_on = None


def upgrade():
    # Add current_time_point column to custom_teaching_structures
    op.add_column('custom_teaching_structures', 
                  sa.Column('current_time_point', sa.String(), nullable=True))


def downgrade():
    # Remove current_time_point column
    op.drop_column('custom_teaching_structures', 'current_time_point')
