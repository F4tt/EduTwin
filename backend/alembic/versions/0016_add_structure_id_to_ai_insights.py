"""Add structure_id to ai_insights table

Revision ID: 0016_add_structure_id_to_ai_insights
Revises: 0015_add_scale_type_to_structure
Create Date: 2024-12-08
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0016_add_structure_id_to_ai_insights'
down_revision = '0015_add_scale_type_to_structure'
branch_labels = None
depends_on = None


def upgrade():
    # Add structure_id column to ai_insights table
    op.add_column('ai_insights', sa.Column('structure_id', sa.Integer(), nullable=True))
    
    # Add foreign key constraint
    op.create_foreign_key(
        'fk_ai_insights_structure_id',
        'ai_insights',
        'custom_teaching_structures',
        ['structure_id'],
        ['id'],
        ondelete='CASCADE'
    )
    
    # Add index for faster queries
    op.create_index('ix_ai_insights_structure_id', 'ai_insights', ['structure_id'])


def downgrade():
    # Remove index
    op.drop_index('ix_ai_insights_structure_id', table_name='ai_insights')
    
    # Remove foreign key constraint
    op.drop_constraint('fk_ai_insights_structure_id', 'ai_insights', type_='foreignkey')
    
    # Remove column
    op.drop_column('ai_insights', 'structure_id')
