"""add scale_type to structure

Revision ID: 0015_add_scale_type_to_structure
Revises: 0014_rename_model_parameters
Create Date: 2025-12-07

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0015_add_scale_type_to_structure'
down_revision = '0014_rename_model_parameters'
branch_labels = None
depends_on = None


def upgrade():
    # Add scale_type column with default value '0-10'
    op.add_column('custom_teaching_structures', 
                  sa.Column('scale_type', sa.String(), server_default='0-10', nullable=False))


def downgrade():
    # Remove scale_type column
    op.drop_column('custom_teaching_structures', 'scale_type')
